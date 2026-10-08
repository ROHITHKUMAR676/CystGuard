from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import require_patient_access, require_patient_doctor
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.database import get_db
from app.mri.models import MRIStudy, StudyMeasurement
from app.schemas.longitudinal import MeasurementCreate, MeasurementRead
from app.services.longitudinal_service import what_changed

router = APIRouter(tags=["Longitudinal MRI"])
Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]


@router.get("/patients/{patient_id}/mri/timeline")
def timeline(patient_id: int, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    studies = list(db.scalars(select(MRIStudy).where(MRIStudy.patient_user_id == patient_id).order_by(MRIStudy.study_date.asc().nullslast(), MRIStudy.uploaded_at.asc())).all())
    dated = [s for s in studies if s.study_date is not None]
    return {"patient_id": patient_id, "ordering_complete": len(dated) == len(studies), "studies": [
        {"id": s.id, "study_date": s.study_date, "uploaded_at": s.uploaded_at,
         "measurements": [MeasurementRead.model_validate(m) for m in s.measurements],
         "assessments": [{"id": a.id, "model_id": a.model_id, "model_version": a.model_version,
                          "risk_class": a.risk_class, "raw_score": a.raw_score, "threshold": a.threshold,
                          "created_at": a.created_at, "score_semantics": "raw model score; not a probability"} for a in s.assessments]}
        for s in studies]}


@router.get("/patients/{patient_id}/mri/compare")
def compare(patient_id: int, previous_study_id: str, current_study_id: str, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    studies = db.scalars(select(MRIStudy).where(MRIStudy.patient_user_id == patient_id,
        MRIStudy.id.in_([previous_study_id, current_study_id]))).all()
    by_id = {s.id: s for s in studies}
    if set(by_id) != {previous_study_id, current_study_id}:
        raise HTTPException(status_code=404, detail="MRI study not found")
    if by_id[previous_study_id].study_date is None or by_id[current_study_id].study_date is None:
        return {"comparison_status": "NOT_CALCULABLE", "doctor_review_required": True, "changes": []}
    if by_id[previous_study_id].study_date >= by_id[current_study_id].study_date:
        raise HTTPException(status_code=422, detail="Studies must be supplied in chronological order")
    return what_changed(by_id[previous_study_id], by_id[current_study_id])


@router.get("/mri/studies/{study_id}/changes")
def changes(study_id: str, previous_study_id: str, db: Db, user: Current):
    current = db.get(MRIStudy, study_id)
    previous = db.get(MRIStudy, previous_study_id)
    if current is None or previous is None or current.patient_user_id is None or current.patient_user_id != previous.patient_user_id:
        raise HTTPException(status_code=404, detail="MRI study not found")
    require_patient_access(db, user, current.patient_user_id)
    return what_changed(previous, current)


@router.post("/mri/studies/{study_id}/measurements", response_model=MeasurementRead, status_code=201)
def add_measurement(study_id: str, payload: MeasurementCreate, db: Db, user: Current):
    study = db.get(MRIStudy, study_id)
    if study is None or user.role is not UserRole.DOCTOR or study.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="MRI study not found")
    if study.patient_user_id is not None:
        require_patient_doctor(db, user, study.patient_user_id)
    item = StudyMeasurement(study_id=study.id, created_by_user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
