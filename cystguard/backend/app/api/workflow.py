from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import require_patient_access, require_patient_doctor
from app.auth.dependencies import get_current_user
from app.auth.models import PatientDoctorAccess, User, UserRole
from app.database import get_db
from app.mri.models import MRIStudy
from app.ocr.models import ConflictReviewStatus, MedicationConflict, MedicationLifecycleStatus, MedicationRecord, OCRVerificationStatus
from app.schemas.workflow import MealCreate, MessageCreate, NoteCreate, ReviewCreate, ReviewResolve, SymptomCreate, SymptomPatch, SymptomRead
from app.schemas.food import MealRead
from app.services.audit_service import record_audit_event
from app.services.careloop_service import record_careloop_event
from app.services.longitudinal_service import what_changed
from app.services.surveillance_service import calculate_plan_status
from app.surveillance.models import SurveillanceEvent, SurveillancePlan
from app.workflow.models import CareLoopEvent, CareMessage, ClinicalNote, MealEntry, ReviewItem, Symptom

router = APIRouter(prefix="/patients", tags=["Patient workflow"])
Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]


@router.get("/{patient_id}/care-profile")
def care_profile(patient_id: int, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    studies = db.scalars(select(MRIStudy).where(MRIStudy.patient_user_id == patient_id)
                         .order_by(MRIStudy.study_date.desc().nullslast(), MRIStudy.uploaded_at.desc())).all()
    patient = db.get(User, patient_id)
    latest = studies[0] if studies else None
    previous = studies[1] if len(studies) > 1 else None
    plans = db.scalars(select(SurveillancePlan).where(SurveillancePlan.patient_user_id == patient_id)
                       .order_by(SurveillancePlan.created_at.desc())).all()
    followup_events = db.scalars(select(SurveillanceEvent).join(SurveillancePlan).where(
        SurveillancePlan.patient_user_id == patient_id).order_by(SurveillanceEvent.planned_date)).all()
    upcoming = []
    for plan in plans:
        computed = calculate_plan_status(plan.target_follow_up_date, datetime.now().date(), plan.status)
        if computed in {"DUE", "OVERDUE", "PLANNED"}:
            upcoming.append({"plan_id": plan.id, "target_date": plan.target_follow_up_date, "status": computed})
    meds = db.scalars(select(MedicationRecord).where(MedicationRecord.patient_id == patient_id,
        MedicationRecord.verification_status == OCRVerificationStatus.VERIFIED,
        MedicationRecord.medication_status == MedicationLifecycleStatus.ACTIVE)
        .order_by(MedicationRecord.created_at.desc()).limit(10)).all()
    symptoms = db.scalars(select(Symptom).where(Symptom.patient_id == patient_id)
                          .order_by(Symptom.recorded_at.desc()).limit(10)).all()
    meals = db.scalars(select(MealEntry).where(MealEntry.patient_id == patient_id)
                       .order_by(MealEntry.recorded_at.desc()).limit(20)).all()
    notes = db.scalars(select(ClinicalNote).where(ClinicalNote.patient_id == patient_id,
        ClinicalNote.author_role == UserRole.DOCTOR.value).order_by(ClinicalNote.created_at.desc()).limit(5)).all()
    open_reviews = db.scalar(select(ReviewItem.id).where(ReviewItem.patient_id == patient_id,
                               ReviewItem.status.in_(["OPEN", "IN_REVIEW"])).limit(1))
    access_rows = db.scalars(select(PatientDoctorAccess).where(PatientDoctorAccess.patient_user_id == patient_id,
                               PatientDoctorAccess.status == "ACTIVE")).all()
    doctors = [db.get(User, r.doctor_user_id) for r in access_rows]
    latest_assessment = latest.assessments[-1] if latest and latest.assessments else None
    return {
        "patient_id": patient_id,
        "identity": {"id": patient_id, "email": patient.email if patient else None},
        "active_doctors": [{"id": d.id, "email": d.email} for d in doctors if d],
        "latest_mri": ({"id": latest.id, "study_date": latest.study_date, "uploaded_at": latest.uploaded_at,
                        "status": latest.status.value} if latest else None),
        "latest_assessment": ({"id": latest_assessment.id, "mri_study_id": latest_assessment.mri_study_id,
            "model_id": latest_assessment.model_id, "model_version": latest_assessment.model_version,
            "risk_class": latest_assessment.risk_class, "raw_score": latest_assessment.raw_score,
            "score_semantics": "raw model score; not a probability", "created_at": latest_assessment.created_at}
            if latest_assessment else None),
        "longitudinal_summary": {"study_count": len(studies), "previous_study_id": previous.id if previous else None,
            "latest_comparison": what_changed(previous, latest) if previous and latest and previous.study_date and latest.study_date and previous.study_date < latest.study_date else None,
            "status": "AVAILABLE" if studies else "UNKNOWN"},
        "surveillance": {"plans": upcoming, "events": [{"event_id": e.id, "plan_id": e.plan_id,
            "event_type": e.event_type, "planned_date": e.planned_date,
            "status": calculate_plan_status(e.planned_date, datetime.now().date(), e.status)}
            for e in followup_events if calculate_plan_status(e.planned_date, datetime.now().date(), e.status) != "CANCELLED"],
            "status": "PENDING_REVIEW" if any(x["status"] in {"DUE", "OVERDUE"} for x in upcoming) else "AVAILABLE" if upcoming else "UNKNOWN"},
        "medications": [{"id": m.id, "status": m.medication_status.value, "verification_status": m.verification_status.value,
                         "details": m.verified_fields, "recorded_at": m.created_at} for m in meds],
        "symptoms": [SymptomRead.model_validate(s).model_dump(mode="json") for s in symptoms],
        "meals": {"status": "AVAILABLE" if meals else "UNKNOWN", "entries": [
            {"id": m.id, "description": m.description, "patient_confirmed": m.patient_confirmed,
             "recorded_at": m.recorded_at} for m in meals]},
        "recent_clinician_notes": {"status": "AVAILABLE" if notes else "UNKNOWN", "items": [
            {"id": n.id, "author_user_id": n.author_user_id, "visibility": n.visibility,
             "source_context": n.source_context, "created_at": n.created_at} for n in notes]},
        "review_queue": {"status": "PENDING_REVIEW" if open_reviews else "UNKNOWN", "has_open_items": bool(open_reviews)},
    }


@router.post("/{patient_id}/symptoms", response_model=SymptomRead, status_code=201)
def create_symptom(patient_id: int, payload: SymptomCreate, db: Db, user: Current):
    if user.role is not UserRole.PATIENT or user.id != patient_id:
        raise HTTPException(status_code=403, detail="Only the patient can record a symptom")
    symptom = Symptom(patient_id=patient_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(symptom)
    db.flush()
    review = ReviewItem(patient_id=patient_id, created_by_user_id=user.id, item_type="PATIENT_SYMPTOM",
                        priority="NORMAL", status="OPEN", source_type="SYMPTOM", source_id=symptom.id,
                        description="Patient-reported symptom awaits clinician review")
    db.add(review)
    db.flush()
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="SYMPTOM_RECORDED",
                          source_type="SYMPTOM", source_id=symptom.id, summary="Patient reported a symptom")
    record_audit_event(db, actor_user_id=user.id, action="SYMPTOM_CREATED", resource_type="SYMPTOM", resource_id=symptom.id)
    record_audit_event(db, actor_user_id=user.id, action="REVIEW_ITEM_CREATED", resource_type="REVIEW_ITEM", resource_id=review.id,
                       metadata={"item_type": "PATIENT_SYMPTOM"})
    db.commit()
    db.refresh(symptom)
    return symptom


@router.get("/{patient_id}/symptoms", response_model=list[SymptomRead])
def list_symptoms(patient_id: int, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    return db.scalars(select(Symptom).where(Symptom.patient_id == patient_id).order_by(Symptom.recorded_at.desc())).all()


@router.patch("/{patient_id}/symptoms/{symptom_id}", response_model=SymptomRead)
def update_symptom(patient_id: int, symptom_id: str, payload: SymptomPatch, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    symptom = db.scalar(select(Symptom).where(Symptom.id == symptom_id, Symptom.patient_id == patient_id))
    if symptom is None:
        raise HTTPException(status_code=404, detail="Symptom not found")
    values = payload.model_dump(exclude_unset=True)
    if user.role is UserRole.DOCTOR:
        if set(values) - {"review_note"}:
            raise HTTPException(status_code=403, detail="Clinicians may review symptoms but cannot edit patient-reported details")
        symptom.review_status = "REVIEWED"
        symptom.reviewed_by_user_id = user.id
        symptom.reviewed_at = datetime.now(timezone.utc)
        symptom.review_note = values.get("review_note")
    else:
        if symptom.created_by_user_id != user.id:
            raise HTTPException(status_code=403, detail="Symptom cannot be edited")
        values.pop("review_note", None)
        for key, value in values.items():
            setattr(symptom, key, value)
    record_audit_event(db, actor_user_id=user.id, action="SYMPTOM_UPDATED", resource_type="SYMPTOM", resource_id=symptom.id)
    db.commit()
    db.refresh(symptom)
    return symptom


@router.post("/{patient_id}/notes", status_code=201)
def create_note(patient_id: int, payload: NoteCreate, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    visibility = payload.visibility
    if user.role is UserRole.PATIENT and visibility != "PATIENT_VISIBLE":
        raise HTTPException(status_code=403, detail="Patient notes must be patient-visible")
    note = ClinicalNote(patient_id=patient_id, author_user_id=user.id, author_role=user.role.value,
                        visibility=visibility, source_context=payload.source_context, body=payload.body)
    db.add(note)
    db.flush()
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="NOTE_CREATED",
                          source_type="CLINICAL_NOTE", source_id=note.id, summary="Care workflow note recorded")
    record_audit_event(db, actor_user_id=user.id, action="CLINICAL_NOTE_CREATED", resource_type="CLINICAL_NOTE", resource_id=note.id,
                       metadata={"visibility": visibility})
    db.commit()
    return {"id": note.id, "patient_id": patient_id, "author_user_id": user.id, "author_role": note.author_role,
            "visibility": note.visibility, "source_context": note.source_context, "body": note.body, "created_at": note.created_at}


@router.get("/{patient_id}/notes")
def list_notes(patient_id: int, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    stmt = select(ClinicalNote).where(ClinicalNote.patient_id == patient_id)
    if user.role is UserRole.PATIENT:
        stmt = stmt.where(ClinicalNote.visibility == "PATIENT_VISIBLE")
    notes = db.scalars(stmt.order_by(ClinicalNote.created_at.desc())).all()
    return [{"id": n.id, "patient_id": n.patient_id, "author_user_id": n.author_user_id, "author_role": n.author_role,
             "visibility": n.visibility, "source_context": n.source_context, "body": n.body, "created_at": n.created_at} for n in notes]


@router.get("/{patient_id}/careloop")
def careloop(patient_id: int, db: Db, user: Current, limit: int = 100):
    require_patient_access(db, user, patient_id)
    limit = min(max(limit, 1), 250)
    events = db.scalars(select(CareLoopEvent).where(CareLoopEvent.patient_id == patient_id)
                        .order_by(CareLoopEvent.occurred_at.desc()).limit(limit)).all()
    return [{"event_id": e.id, "patient_id": e.patient_id, "event_type": e.event_type, "source_type": e.source_type,
             "source_id": e.source_id, "occurred_at": e.occurred_at, "status": e.status, "summary": e.summary} for e in events]


@router.get("/{patient_id}/visit-preparation")
def visit_preparation(patient_id: int, db: Db, user: Current):
    require_patient_doctor(db, user, patient_id)
    profile = care_profile(patient_id, db, user)
    recent_symptoms = profile["symptoms"]
    open_reviews = db.scalars(select(ReviewItem).where(ReviewItem.patient_id == patient_id,
        ReviewItem.status.in_(["OPEN", "IN_REVIEW"])).order_by(ReviewItem.created_at.desc()).limit(50)).all()
    latest = db.scalar(select(MRIStudy).where(MRIStudy.patient_user_id == patient_id)
                       .order_by(MRIStudy.study_date.desc().nullslast(), MRIStudy.uploaded_at.desc()).limit(1))
    previous = None
    if latest:
        previous = db.scalar(select(MRIStudy).where(MRIStudy.patient_user_id == patient_id, MRIStudy.id != latest.id)
                             .order_by(MRIStudy.study_date.desc().nullslast(), MRIStudy.uploaded_at.desc()).limit(1))
    summary = {"patient_id": patient_id, "latest_mri": profile["latest_mri"],
        "previous_mri_id": previous.id if previous else None,
        "factual_changes": what_changed(previous, latest) if previous and latest and previous.study_date and latest.study_date and previous.study_date < latest.study_date else None,
        "latest_assessment": profile["latest_assessment"], "kyoto_assessment": {"status": "UNKNOWN", "value": None},
        "trust_concordance": {"status": "UNKNOWN", "value": None}, "surveillance": profile["surveillance"],
        "symptoms": recent_symptoms, "medications": profile["medications"], "meals": profile["meals"],
        "unresolved_reviews": [{"review_id": r.id, "type": r.item_type, "status": r.status, "priority": r.priority} for r in open_reviews],
        "missing_data": ["persisted Kyoto/trust results", "confirmed meals/nutrition", "historical clinician notes"],
        "diagnosis": None, "treatment_recommendations": [], "medication_recommendations": [], "surgery_recommendations": []}
    record_audit_event(db, actor_user_id=user.id, action="VISIT_PREPARATION_GENERATED", resource_type="PATIENT", resource_id=str(patient_id))
    db.commit()
    return summary


@router.get("/{patient_id}/reviews")
def list_reviews(patient_id: int, db: Db, user: Current, status: str | None = None):
    require_patient_doctor(db, user, patient_id)
    stmt = select(ReviewItem).where(ReviewItem.patient_id == patient_id)
    if status:
        if status not in {"OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"}:
            raise HTTPException(status_code=422, detail="Invalid review status")
        stmt = stmt.where(ReviewItem.status == status)
    items = db.scalars(stmt.order_by(ReviewItem.created_at.desc())).all()
    return items


@router.post("/{patient_id}/reviews", status_code=201)
def create_review(patient_id: int, payload: ReviewCreate, db: Db, user: Current):
    require_patient_doctor(db, user, patient_id)
    item = ReviewItem(patient_id=patient_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="CLINICIAN_REVIEW_PENDING",
                          source_type="REVIEW_ITEM", source_id=item.id, status="PENDING_REVIEW")
    record_audit_event(db, actor_user_id=user.id, action="REVIEW_ITEM_CREATED", resource_type="REVIEW_ITEM", resource_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{patient_id}/reviews/{review_id}/resolve")
def resolve_review(patient_id: int, review_id: str, payload: ReviewResolve, db: Db, user: Current):
    require_patient_doctor(db, user, patient_id)
    item = db.scalar(select(ReviewItem).where(ReviewItem.id == review_id, ReviewItem.patient_id == patient_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Review item is already closed")
    item.status, item.resolved_at, item.resolved_by_user_id = payload.status, datetime.now(timezone.utc), user.id
    item.resolution_note = payload.resolution_note
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="CLINICIAN_REVIEW_COMPLETED",
                          source_type="REVIEW_ITEM", source_id=item.id, status=payload.status)
    record_audit_event(db, actor_user_id=user.id, action="REVIEW_ITEM_RESOLVED", resource_type="REVIEW_ITEM", resource_id=item.id,
                       metadata={"status": payload.status})
    db.commit()
    db.refresh(item)
    return item


@router.get("/{patient_id}/meals", response_model=list[MealRead])
def list_meals(patient_id: int, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    rows = db.scalars(select(MealEntry).where(MealEntry.patient_id == patient_id)
                      .order_by(MealEntry.recorded_at.desc())).all()
    return [MealRead.model_validate(row) for row in rows]


@router.post("/{patient_id}/meals", status_code=201)
def create_meal(patient_id: int, payload: MealCreate, db: Db, user: Current):
    if user.role is not UserRole.PATIENT or user.id != patient_id:
        raise HTTPException(status_code=403, detail="Only the patient can record a meal")
    row = MealEntry(patient_id=patient_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(row)
    db.flush()
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="MEAL_RECORDED",
                          source_type="MEAL_ENTRY", source_id=row.id, summary="Patient recorded a meal")
    record_audit_event(db, actor_user_id=user.id, action="MEAL_CREATED", resource_type="MEAL_ENTRY", resource_id=row.id)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "patient_id": row.patient_id, "description": row.description,
            "patient_confirmed": row.patient_confirmed, "recorded_at": row.recorded_at}


@router.get("/{patient_id}/messages")
def list_messages(patient_id: int, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    rows = db.scalars(select(CareMessage).where(CareMessage.patient_id == patient_id)
                      .order_by(CareMessage.created_at.asc())).all()
    return [{"id": row.id, "patient_id": row.patient_id, "sender_user_id": row.sender_user_id,
             "sender_name": (db.get(User, row.sender_user_id).display_name if db.get(User, row.sender_user_id) else None),
             "sender_role": db.get(User, row.sender_user_id).role.value if db.get(User, row.sender_user_id) else None,
             "body": row.body, "created_at": row.created_at} for row in rows]


@router.post("/{patient_id}/messages", status_code=201)
def create_message(patient_id: int, payload: MessageCreate, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    if user.role is UserRole.PATIENT:
        connected_doctor = db.scalar(select(PatientDoctorAccess.id).where(
            PatientDoctorAccess.patient_user_id == patient_id,
            PatientDoctorAccess.status == "ACTIVE").limit(1))
        if connected_doctor is None:
            raise HTTPException(status_code=409, detail="Connect with a clinician before sending a care-team message")
    row = CareMessage(patient_id=patient_id, sender_user_id=user.id, body=payload.body)
    db.add(row)
    db.flush()
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="CARE_MESSAGE_SENT",
                          source_type="CARE_MESSAGE", source_id=row.id, summary="Care-team message sent")
    record_audit_event(db, actor_user_id=user.id, action="CARE_MESSAGE_CREATED", resource_type="CARE_MESSAGE", resource_id=row.id)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "patient_id": row.patient_id, "sender_user_id": row.sender_user_id,
            "sender_name": user.display_name, "sender_role": user.role.value,
            "body": row.body, "created_at": row.created_at}
