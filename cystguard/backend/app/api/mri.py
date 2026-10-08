from typing import Annotated

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.auth.access import require_patient_doctor
from app.database import get_db
from app.ml.ml_service import MLService, get_ml_service
from app.schemas.mri import AssessmentRead, MRIAnalysisResponse, MRIStudyRead
from app.services.analysis_service import (
    create_and_analyze_study,
    get_latest_assessment,
    get_accessible_assessment,
    get_accessible_study,
)
from app.storage.service import StorageBackend, get_storage
from app.services.careloop_service import record_careloop_event
from app.services.audit_service import record_audit_event
from app.clinical.assessment_pipeline import empty_clinical_context, evaluate_and_persist
from app.explanation.explanation_service import build_explanation
from app.schemas.clinical_assessment import ClinicalAssessmentInput, CystType
from app.mri.viewer import render_slice, volume_metadata
from fastapi.responses import Response

router = APIRouter(prefix="/mri", tags=["MRI"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _require_doctor(user: User) -> None:
    if user.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor access is required.")


@router.post("/studies", response_model=MRIAnalysisResponse, status_code=status.HTTP_201_CREATED)
def upload_mri(
    upload: Annotated[UploadFile, File(description="T1-weighted NIfTI MRI file (.nii or .nii.gz)")],
    db: DbSession,
    current_user: CurrentUser,
    storage: Annotated[StorageBackend, Depends(get_storage)],
    ml_service: Annotated[MLService, Depends(get_ml_service)],
    patient_id: Annotated[int | None, Form()] = None,
    study_date: Annotated[date | None, Form()] = None,
) -> MRIAnalysisResponse:
    _require_doctor(current_user)
    if patient_id is not None:
        require_patient_doctor(db, current_user, patient_id)
    study, assessment = create_and_analyze_study(upload, current_user, db, storage, ml_service,
                                                   patient_user_id=patient_id, study_date=study_date)
    evaluate_and_persist(assessment, CystType.UNKNOWN, empty_clinical_context())
    db.commit()
    if patient_id is not None:
        record_careloop_event(db, patient_id=patient_id, actor_user_id=current_user.id,
                              event_type="MRI_COMPLETED", source_type="MRI_STUDY", source_id=study.id,
                              summary="MRI upload and analysis workflow completed")
        record_audit_event(db, actor_user_id=current_user.id, action="MRI_PATIENT_LINKED",
                           resource_type="MRI_STUDY", resource_id=study.id, metadata={"patient_id": patient_id})
        db.commit()
    return MRIAnalysisResponse(
        mri_study=MRIStudyRead.model_validate(study),
        assessment=AssessmentRead.model_validate(assessment),
    )


@router.get("/studies/{study_id}", response_model=MRIAnalysisResponse)
def read_mri_study(
    study_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> MRIAnalysisResponse:
    _require_doctor(current_user)
    study = get_accessible_study(db, study_id, current_user)
    assessment = get_latest_assessment(study)
    return MRIAnalysisResponse(
        mri_study=MRIStudyRead.model_validate(study),
        assessment=AssessmentRead.model_validate(assessment),
    )


@router.get("/assessments/{assessment_id}", response_model=AssessmentRead)
def read_assessment(
    assessment_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> AssessmentRead:
    _require_doctor(current_user)
    assessment = get_accessible_assessment(db, assessment_id, current_user)
    return AssessmentRead.model_validate(assessment)


@router.post("/assessments/{assessment_id}/clinical-context", response_model=AssessmentRead)
def update_clinical_context(
    assessment_id: str,
    body: ClinicalAssessmentInput,
    db: DbSession,
    current_user: CurrentUser,
) -> AssessmentRead:
    _require_doctor(current_user)
    assessment = get_accessible_assessment(db, assessment_id, current_user)
    evaluate_and_persist(assessment, body.cyst_type, body.clinical_context)
    db.commit()
    db.refresh(assessment)
    return AssessmentRead.model_validate(assessment)


@router.post("/assessments/{assessment_id}/explanation", response_model=AssessmentRead)
def regenerate_explanation(
    assessment_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> AssessmentRead:
    _require_doctor(current_user)
    assessment = get_accessible_assessment(db, assessment_id, current_user)
    if not assessment.guideline_result or not assessment.trust_result:
        raise HTTPException(status_code=409, detail="Structured assessment is not available yet.")
    facts = {
        "ai": {"model_id": assessment.model_id, "model_version": assessment.model_version,
               "risk_class": assessment.risk_class, "raw_score": assessment.raw_score,
               "threshold": assessment.threshold, "prediction_status": assessment.prediction_status.value,
               "input_quality_status": assessment.input_quality_status.value},
        "input_quality": {"status": assessment.input_quality_status.value},
        "clinical_context": assessment.clinical_context,
        "guideline": assessment.guideline_result,
        "trust": assessment.trust_result,
        "concordance": assessment.trust_result.get("concordance"),
        "longitudinal": (assessment.clinical_context or {}).get("longitudinal_measurements") or {"status": "UNAVAILABLE"},
    }
    assessment.explanation_result = build_explanation(facts)
    db.commit()
    db.refresh(assessment)
    return AssessmentRead.model_validate(assessment)


@router.get("/studies/{study_id}/volume")
def read_volume_metadata(
    study_id: str,
    db: DbSession,
    current_user: CurrentUser,
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> dict:
    _require_doctor(current_user)
    study = get_accessible_study(db, study_id, current_user)
    try:
        return volume_metadata(study, storage)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Stored MRI volume cannot be displayed.") from exc


@router.get("/studies/{study_id}/volume/{plane}/{index}.png")
def read_volume_slice(
    study_id: str,
    plane: str,
    index: int,
    db: DbSession,
    current_user: CurrentUser,
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> Response:
    _require_doctor(current_user)
    study = get_accessible_study(db, study_id, current_user)
    try:
        image = render_slice(study, storage, plane, index)
    except IndexError as exc:
        raise HTTPException(status_code=416, detail="MRI slice index is outside the volume.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Stored MRI volume cannot be displayed.") from exc
    return Response(content=image, media_type="image/png", headers={"Cache-Control": "private, no-store"})
