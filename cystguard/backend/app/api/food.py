from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from io import BytesIO
import logging
import math
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import require_patient_access, require_patient_doctor
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.config import get_settings
from app.database import get_db
from app.food.food_provider import FoodAnalysisError, FoodProvider, FoodProviderUnavailable
from app.food.foodcnn_adapter import FoodCNNAdapter
from app.food.nutrition_rules import meal_context_flags, nutrition_alerts
from app.schemas.food import MealConfirmation, MealPatch, MealRead, NutritionObservationCreate, NutritionProfileUpdate
from app.services.audit_service import record_audit_event
from app.services.careloop_service import record_careloop_event
from app.storage.service import StorageBackend, get_storage
from app.workflow.models import MealEntry, NutritionObservation, NutritionProfile

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Meal analysis and nutrition monitoring"])
Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]
Storage = Annotated[StorageBackend, Depends(get_storage)]


@lru_cache(maxsize=1)
def get_food_provider() -> FoodProvider:
    settings = get_settings()
    return FoodCNNAdapter(settings.foodcnn_checkpoint_path, settings.foodcnn_model_version)


Provider = Annotated[FoodProvider, Depends(get_food_provider)]


def _require_patient_self(user: User) -> None:
    if user.role is not UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can submit or confirm their meals.")


def _meal_for_patient(db: Session, meal_id: str, patient_id: int) -> MealEntry:
    meal = db.scalar(select(MealEntry).where(MealEntry.id == meal_id, MealEntry.patient_id == patient_id))
    if meal is None:
        raise HTTPException(status_code=404, detail="Meal not found.")
    return meal


def _raw_values(result) -> dict[str, float]:
    return {key: float(value) for key, value in result.nutrients.items()}


@router.post("/food/meals/analyze", response_model=MealRead, status_code=status.HTTP_201_CREATED)
def analyze_meal(
    upload: Annotated[UploadFile, File()],
    current_user: Current,
    db: Db,
    storage: Storage,
    provider: Provider,
    description: Annotated[str, Form()] = "",
) -> MealRead:
    _require_patient_self(current_user)
    settings = get_settings()
    if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP meal image.")
    image = upload.file.read(settings.max_meal_upload_size_mb * 1024 * 1024 + 1)
    if not image:
        raise HTTPException(status_code=422, detail="The meal image is empty.")
    if len(image) > settings.max_meal_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="The meal image exceeds the configured upload limit.")
    try:
        result = provider.analyze(image)
    except FoodAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FoodProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Food provider failed during meal analysis")
        raise HTTPException(status_code=503, detail="Meal analysis is temporarily unavailable; no estimate was saved.") from exc

    try:
        nutrition = _raw_values(result)
        portion = float(result.estimated_portion_grams)
    except (TypeError, ValueError, AttributeError):
        nutrition, portion = {}, float("nan")
    required_nutrients = {"calories_kcal", "fat_g", "carbohydrates_g", "protein_g"}
    if (set(nutrition) != required_nutrients or
            any(not math.isfinite(value) or value < 0 for value in nutrition.values()) or
            not math.isfinite(portion) or portion <= 0):
        raise HTTPException(status_code=422, detail="Food provider returned an invalid estimate; no meal was saved.")
    stored = None
    try:
        stored = storage.store(BytesIO(image), upload.filename or "meal-image", upload.content_type)
        meal = MealEntry(
            patient_id=current_user.id,
            created_by_user_id=current_user.id,
            description=description.strip(),
            patient_confirmed=False,
            analysis_status="AWAITING_CONFIRMATION",
            food_image_key=stored.key,
            food_image_content_type=upload.content_type,
            food_items=[],
            food_context_tags=[],
            nutrition_context_flags=[],
            raw_provider_output=dict(result.raw_output),
            nutrition_estimate={**nutrition, "estimated_portion_grams": portion},
            estimated_portion_grams=portion,
            recognition_confidence=result.recognition_confidence,
            food_provider=result.provider,
            food_provider_version=result.provider_version,
            food_model_version=result.model_version,
            nutrition_source=result.nutrition_source,
            nutrition_source_version=result.nutrition_source_version,
            nutrition_estimation_method=result.estimation_method,
        )
        db.add(meal)
        db.flush()
        record_careloop_event(db, patient_id=current_user.id, actor_user_id=current_user.id,
            event_type="MEAL_ESTIMATE_CREATED", source_type="MEAL_ENTRY", source_id=meal.id,
            summary="An estimated meal record is awaiting patient confirmation")
        record_audit_event(db, actor_user_id=current_user.id, action="MEAL_ESTIMATE_CREATED",
            resource_type="MEAL_ENTRY", resource_id=meal.id)
        db.commit()
        db.refresh(meal)
        return MealRead.model_validate(meal)
    except Exception:
        db.rollback()
        if stored is not None:
            storage.delete(stored.key)
        raise


@router.post("/food/meals/{meal_id}/confirm", response_model=MealRead)
def confirm_meal(meal_id: str, payload: MealConfirmation, db: Db, current_user: Current) -> MealRead:
    _require_patient_self(current_user)
    meal = _meal_for_patient(db, meal_id, current_user.id)
    if meal.nutrition_estimate is None:
        raise HTTPException(status_code=409, detail="This meal has no image-based estimate to confirm.")
    if meal.analysis_status == "CONFIRMED_MEAL":
        raise HTTPException(status_code=409, detail="This meal is already confirmed; use PATCH to correct it.")

    estimated = dict(meal.nutrition_estimate)
    corrections = {"description": payload.description, "food_items": payload.food_items,
                   "food_context_tags": payload.food_context_tags}
    final_nutrition = dict(estimated)
    if payload.nutrition is not None:
        corrected = payload.nutrition.model_dump(exclude_unset=True)
        final_nutrition.update(corrected)
        if corrected:
            corrections["nutrition"] = corrected
    portion = payload.estimated_portion_grams or meal.estimated_portion_grams
    if payload.estimated_portion_grams is not None:
        corrections["estimated_portion_grams"] = payload.estimated_portion_grams

    meal.description = payload.description.strip()
    meal.food_items = [item.strip() for item in payload.food_items if item.strip()]
    meal.food_context_tags = list(dict.fromkeys(payload.food_context_tags))
    meal.patient_corrections = corrections
    meal.estimated_portion_grams = portion
    profile = db.get(NutritionProfile, current_user.id)
    meal_day_start = datetime.combine(meal.recorded_at.date(), time.min, tzinfo=timezone.utc)
    observations = db.scalars(select(NutritionObservation).where(
        NutritionObservation.patient_id == current_user.id,
        NutritionObservation.recorded_at >= meal_day_start,
        NutritionObservation.recorded_at < meal_day_start + timedelta(days=1),
    ).order_by(NutritionObservation.recorded_at.desc())).all()
    reported = list(dict.fromkeys(symptom for row in observations for symptom in (row.reported_symptoms or [])))
    flags = meal_context_flags(meal.food_context_tags, reported,
        documented_pei_pert=bool(profile and profile.documented_pei_pert),
        documented_diabetes=bool(profile and profile.documented_diabetes))
    for flag in flags:
        flag["reported_symptoms"] = [symptom for symptom in reported]
    meal.nutrition_context_flags = flags
    if payload.confirmed:
        meal.patient_confirmed = True
        meal.analysis_status = "CONFIRMED_MEAL"
        meal.final_nutrition = final_nutrition
        record_careloop_event(db, patient_id=current_user.id, actor_user_id=current_user.id,
            event_type="MEAL_CONFIRMED", source_type="MEAL_ENTRY", source_id=meal.id,
            summary="Patient confirmed or corrected the meal estimate")
        action = "MEAL_CONFIRMED"
    else:
        meal.patient_confirmed = False
        meal.analysis_status = "UNCERTAIN"
        meal.final_nutrition = None
        action = "MEAL_MARKED_UNCERTAIN"
    record_audit_event(db, actor_user_id=current_user.id, action=action,
        resource_type="MEAL_ENTRY", resource_id=meal.id)
    db.commit()
    db.refresh(meal)
    return MealRead.model_validate(meal)


@router.patch("/food/meals/{meal_id}", response_model=MealRead)
def patch_meal(meal_id: str, payload: MealPatch, db: Db, current_user: Current) -> MealRead:
    _require_patient_self(current_user)
    meal = _meal_for_patient(db, meal_id, current_user.id)
    if not meal.patient_confirmed:
        raise HTTPException(status_code=409, detail="Confirm the meal before editing its saved values.")
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return MealRead.model_validate(meal)
    corrections = dict(meal.patient_corrections or {})
    for key, value in values.items():
        if key == "nutrition" and value is not None:
            value = {**(meal.final_nutrition or meal.nutrition_estimate or {}),
                     **{k: v for k, v in value.items() if v is not None}}
            corrections[key] = value
            if meal.patient_confirmed:
                meal.final_nutrition = value
        elif key == "description":
            meal.description = value.strip()
            corrections[key] = value.strip()
        elif key == "food_items":
            meal.food_items = [item.strip() for item in (value or []) if item.strip()]
            corrections[key] = meal.food_items
        elif key == "food_context_tags":
            meal.food_context_tags = list(dict.fromkeys(value or []))
            corrections[key] = meal.food_context_tags
        elif key == "estimated_portion_grams":
            meal.estimated_portion_grams = value
            corrections[key] = value
    meal.patient_corrections = corrections
    record_audit_event(db, actor_user_id=current_user.id, action="MEAL_CORRECTED",
        resource_type="MEAL_ENTRY", resource_id=meal.id)
    db.commit()
    db.refresh(meal)
    return MealRead.model_validate(meal)


@router.get("/food/meals/{meal_id}/image")
def read_meal_image(meal_id: str, db: Db, current_user: Current, storage: Storage):
    meal = db.get(MealEntry, meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail="Meal not found.")
    require_patient_access(db, current_user, meal.patient_id)
    if not meal.food_image_key:
        raise HTTPException(status_code=404, detail="No image is stored for this meal.")
    try:
        image = storage.open(meal.food_image_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Meal image is no longer available.") from exc
    return StreamingResponse(image, media_type=meal.food_image_content_type or "application/octet-stream",
        headers={"Cache-Control": "private, no-store"})


@router.post("/patients/{patient_id}/nutrition/profile", response_model=dict)
def update_nutrition_profile(patient_id: int, payload: NutritionProfileUpdate, db: Db, current_user: Current) -> dict:
    require_patient_doctor(db, current_user, patient_id)
    profile = db.get(NutritionProfile, patient_id)
    if profile is None:
        profile = NutritionProfile(patient_id=patient_id, created_by_user_id=current_user.id)
        db.add(profile)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    profile.created_by_user_id = current_user.id
    db.commit()
    db.refresh(profile)
    return {"patient_id": profile.patient_id, "target_daily_kcal": profile.target_daily_kcal,
        "target_daily_protein_g": profile.target_daily_protein_g, "documented_pei_pert": profile.documented_pei_pert,
        "documented_diabetes": profile.documented_diabetes, "updated_at": profile.updated_at}


@router.post("/patients/{patient_id}/nutrition/observations", response_model=dict, status_code=201)
def create_nutrition_observation(patient_id: int, payload: NutritionObservationCreate,
                                 db: Db, current_user: Current) -> dict:
    if current_user.role is not UserRole.PATIENT or current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Patients can record only their own nutrition observations.")
    if payload.weight_kg is None and payload.appetite == "UNKNOWN" and not payload.reported_symptoms and not payload.intake_day_complete:
        raise HTTPException(status_code=422, detail="Record a weight, appetite, or nutrition-impact symptom.")
    observation = NutritionObservation(patient_id=patient_id, recorded_by_user_id=current_user.id,
        **payload.model_dump())
    db.add(observation)
    db.flush()
    record_careloop_event(db, patient_id=patient_id, actor_user_id=current_user.id,
        event_type="NUTRITION_OBSERVATION_RECORDED", source_type="NUTRITION_OBSERVATION",
        source_id=observation.id, summary="Patient recorded nutrition monitoring information")
    record_audit_event(db, actor_user_id=current_user.id, action="NUTRITION_OBSERVATION_RECORDED",
        resource_type="NUTRITION_OBSERVATION", resource_id=observation.id)
    db.commit()
    db.refresh(observation)
    return _observation_read(observation)


def _observation_read(row: NutritionObservation) -> dict:
    bmi = None
    if row.weight_kg and row.height_cm:
        bmi = round(row.weight_kg / ((row.height_cm / 100) ** 2), 1)
    return {"id": row.id, "weight_kg": row.weight_kg, "height_cm": row.height_cm, "bmi": bmi,
        "appetite": row.appetite, "reported_symptoms": row.reported_symptoms or [],
        "intake_interfered": row.intake_interfered, "intake_day_complete": row.intake_day_complete,
        "recorded_at": row.recorded_at}


@router.get("/patients/{patient_id}/nutrition/summary")
def nutrition_summary(patient_id: int, db: Db, current_user: Current) -> dict:
    require_patient_access(db, current_user, patient_id)
    today = datetime.now(timezone.utc).date()
    since = datetime.combine(today - timedelta(days=90), time.min, tzinfo=timezone.utc)
    meals = db.scalars(select(MealEntry).where(MealEntry.patient_id == patient_id,
        MealEntry.recorded_at >= since).order_by(MealEntry.recorded_at.desc())).all()
    observations = db.scalars(select(NutritionObservation).where(
        NutritionObservation.patient_id == patient_id,
        NutritionObservation.recorded_at >= since).order_by(NutritionObservation.recorded_at.desc())).all()
    profile = db.get(NutritionProfile, patient_id)
    daily: dict[date, dict] = defaultdict(lambda: {
        "calories_kcal": 0.0, "protein_g": 0.0, "carbohydrates_g": 0.0, "fat_g": 0.0,
        "meal_count": 0, "confirmed_count": 0, "has_estimate": False,
    })
    for meal in meals:
        # Pending/uncertain image estimates remain visible in meal history but are
        # excluded from intake totals until the patient confirms/corrects them.
        nutrients = meal.final_nutrition if meal.patient_confirmed else None
        if not nutrients:
            continue
        day = meal.recorded_at.date()
        entry = daily[day]
        entry["meal_count"] += 1
        entry["confirmed_count"] += int(meal.patient_confirmed)
        entry["has_estimate"] = True
        for nutrient in ("calories_kcal", "protein_g", "carbohydrates_g", "fat_g"):
            if nutrients.get(nutrient) is not None:
                entry[nutrient] += float(nutrients[nutrient])
    recorded_complete_days = {row.recorded_at.date() for row in observations if row.intake_day_complete}
    complete_days = {day for day in recorded_complete_days if daily[day]["has_estimate"]}
    for day in complete_days:
        daily[day]["day_complete"] = True
    populated = [values for values in daily.values() if values["meal_count"]]
    average = None
    if populated:
        average = {key: round(sum(item[key] for item in populated) / len(populated), 1)
            for key in ("calories_kcal", "protein_g", "carbohydrates_g", "fat_g")}
    observation_data = []
    for row in observations:
        parsed = _observation_read(row)
        parsed["date"] = row.recorded_at.date()
        observation_data.append(parsed)
    meal_contexts = []
    for meal in meals:
        if meal.nutrition_context_flags:
            meal_contexts.append({"date": meal.recorded_at.date(),
                "context_codes": [item.get("code") for item in meal.nutrition_context_flags],
                "symptoms": list(dict.fromkeys(symptom for item in meal.nutrition_context_flags
                    for symptom in item.get("reported_symptoms", [])))})
    alerts = nutrition_alerts(
        daily_totals=daily, complete_days=complete_days, observations=observation_data,
        meal_contexts=meal_contexts, target_daily_kcal=profile.target_daily_kcal if profile else None,
        today=today)
    daily_rows = []
    for day in sorted(set(daily) | recorded_complete_days)[-14:]:
        value = dict(daily[day])
        target = profile.target_daily_kcal if profile else None
        value["percent_of_recorded_target"] = round(value["calories_kcal"] / target * 100, 1) if target and day in complete_days else None
        daily_rows.append({"date": day.isoformat(), **value})
    latest_weight = next((row for row in observations if row.weight_kg is not None), None)
    latest_height = next((row.height_cm for row in observations if row.height_cm is not None), None)
    latest_bmi = round(latest_weight.weight_kg / ((latest_height / 100) ** 2), 1) if latest_weight and latest_height else None
    return {
        "patient_id": patient_id,
        "period_days": 90,
        "daily_estimates": daily_rows,
        "average_per_logged_day": average,
        "average_basis": "days with at least one analyzed meal; not a complete-day intake measure",
        "recorded_target": {"daily_kcal": profile.target_daily_kcal if profile else None,
            "daily_protein_g": profile.target_daily_protein_g if profile else None,
            "source": "clinician-entered" if profile and (profile.target_daily_kcal or profile.target_daily_protein_g) else None},
        "target_notice": "No individualized nutrition target has been recorded." if not profile or not profile.target_daily_kcal else None,
        "weight": {"latest_kg": latest_weight.weight_kg if latest_weight else None,
            "latest_recorded_at": latest_weight.recorded_at if latest_weight else None,
            "height_cm": latest_height, "bmi": latest_bmi,
            "history": [{"weight_kg": item["weight_kg"], "date": item["date"].isoformat()} for item in observation_data if item["weight_kg"] is not None]},
        "appetite_history": [{"appetite": item["appetite"], "reported_symptoms": item["reported_symptoms"],
            "intake_interfered": item["intake_interfered"], "date": item["date"].isoformat()} for item in observation_data],
        "documented_context": {"pei_pert": bool(profile and profile.documented_pei_pert),
            "diabetes": bool(profile and profile.documented_diabetes)},
        "alerts": alerts,
        "alert_disclaimer": "These are monitoring flags for clinician or dietitian review, not diagnoses or automatic diet or medication instructions.",
        "meals": [MealRead.model_validate(meal).model_dump(mode="json") for meal in meals],
    }
