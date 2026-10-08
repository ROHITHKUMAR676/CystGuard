from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import PatientDoctorAccess, User, UserRole
from app.database import get_db
from app.services.audit_service import record_audit_event
from app.services.careloop_service import record_careloop_event

router = APIRouter(prefix="/patients", tags=["Patient access"])
Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]


class AccessRequestCreate(BaseModel):
    doctor_access_code: str = Field(min_length=4, max_length=24)


class PatientInvite(BaseModel):
    email: str = Field(min_length=3, max_length=320)


def _access_read(db: Session, relation: PatientDoctorAccess) -> dict:
    patient = db.get(User, relation.patient_user_id)
    doctor = db.get(User, relation.doctor_user_id)
    return {
        "patient_id": relation.patient_user_id,
        "patient_name": patient.display_name if patient else None,
        "patient_email": patient.email if patient else None,
        "doctor_id": relation.doctor_user_id,
        "doctor_name": doctor.display_name if doctor else None,
        "doctor_email": doctor.email if doctor else None,
        "doctor_access_code": doctor.access_code if doctor else None,
        "status": relation.status,
        "created_at": relation.granted_at,
        "updated_at": relation.revoked_at,
    }


@router.post("/access-requests", status_code=201)
def request_doctor_access(payload: AccessRequestCreate, db: Db, user: Current):
    if user.role is not UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can request clinician access")
    doctor = db.scalar(select(User).where(
        User.access_code == payload.doctor_access_code.strip().upper(), User.role == UserRole.DOCTOR))
    if doctor is None:
        raise HTTPException(status_code=404, detail="Clinician access code was not found")
    relation = db.query(PatientDoctorAccess).filter_by(
        patient_user_id=user.id, doctor_user_id=doctor.id).first()
    if relation is None:
        relation = PatientDoctorAccess(patient_user_id=user.id, doctor_user_id=doctor.id, status="PENDING")
        db.add(relation)
    elif relation.status == "ACTIVE":
        return _access_read(db, relation)
    else:
        relation.status, relation.granted_at, relation.revoked_at = "PENDING", datetime.now(timezone.utc), None
    db.flush()
    record_audit_event(db, actor_user_id=user.id, action="PATIENT_ACCESS_REQUESTED",
                       resource_type="PATIENT_DOCTOR_ACCESS", resource_id=str(relation.id),
                       metadata={"doctor_user_id": doctor.id})
    record_careloop_event(db, patient_id=user.id, actor_user_id=user.id, event_type="DOCTOR_ACCESS_REQUESTED",
                          source_type="PATIENT_DOCTOR_ACCESS", source_id=str(relation.id),
                          summary="Patient requested clinician access")
    db.commit()
    db.refresh(relation)
    return _access_read(db, relation)


@router.get("/access-requests")
def list_doctor_access_requests(db: Db, user: Current):
    if user.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Doctor access is required")
    rows = db.scalars(select(PatientDoctorAccess).where(
        PatientDoctorAccess.doctor_user_id == user.id).order_by(PatientDoctorAccess.granted_at.desc())).all()
    return [_access_read(db, row) for row in rows]


@router.get("/directory")
def list_connected_patients(db: Db, user: Current):
    if user.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Doctor access is required")
    rows = db.scalars(select(PatientDoctorAccess).where(
        PatientDoctorAccess.doctor_user_id == user.id,
        PatientDoctorAccess.status == "ACTIVE").order_by(PatientDoctorAccess.granted_at.desc())).all()
    return [_access_read(db, row) for row in rows]


@router.post("/access-requests/invite", status_code=201)
def invite_existing_patient(payload: PatientInvite, db: Db, user: Current):
    if user.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Doctor access is required")
    email = payload.email.strip().lower()
    patient = db.scalar(select(User).where(User.email == email, User.role == UserRole.PATIENT))
    if patient is None:
        raise HTTPException(status_code=404, detail="No patient account uses this email yet")
    relation = db.query(PatientDoctorAccess).filter_by(
        patient_user_id=patient.id, doctor_user_id=user.id).first()
    if relation is None:
        relation = PatientDoctorAccess(patient_user_id=patient.id, doctor_user_id=user.id, status="PENDING")
        db.add(relation)
    elif relation.status == "ACTIVE":
        raise HTTPException(status_code=409, detail="Patient is already connected")
    else:
        relation.status, relation.granted_at, relation.revoked_at = "PENDING", datetime.now(timezone.utc), None
    db.flush()
    record_audit_event(db, actor_user_id=user.id, action="PATIENT_ACCESS_INVITED",
                       resource_type="PATIENT_DOCTOR_ACCESS", resource_id=str(relation.id),
                       metadata={"patient_user_id": patient.id})
    record_careloop_event(db, patient_id=patient.id, actor_user_id=user.id, event_type="DOCTOR_ACCESS_INVITED",
                          source_type="PATIENT_DOCTOR_ACCESS", source_id=str(relation.id),
                          summary="Clinician requested a patient connection")
    db.commit()
    db.refresh(relation)
    return _access_read(db, relation)


@router.post("/{patient_id}/doctors/{doctor_id}/approve-access")
def approve_access(patient_id: int, doctor_id: int, db: Db, user: Current):
    if user.role is not UserRole.DOCTOR or user.id != doctor_id:
        raise HTTPException(status_code=403, detail="Only the requested doctor can approve access")
    relation = db.query(PatientDoctorAccess).filter_by(
        patient_user_id=patient_id, doctor_user_id=doctor_id, status="PENDING").first()
    if relation is None:
        raise HTTPException(status_code=404, detail="Pending access request not found")
    relation.status, relation.granted_at, relation.revoked_at = "ACTIVE", datetime.now(timezone.utc), None
    record_audit_event(db, actor_user_id=user.id, action="PATIENT_ACCESS_APPROVED",
                       resource_type="PATIENT_DOCTOR_ACCESS", resource_id=str(relation.id),
                       metadata={"patient_user_id": patient_id})
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="DOCTOR_ACCESS_APPROVED",
                          source_type="PATIENT_DOCTOR_ACCESS", source_id=str(relation.id),
                          summary="Clinician approved patient access")
    db.commit()
    db.refresh(relation)
    return _access_read(db, relation)


@router.post("/{patient_id}/doctors/{doctor_id}/decline-access")
def decline_access(patient_id: int, doctor_id: int, db: Db, user: Current):
    if user.role is not UserRole.DOCTOR or user.id != doctor_id:
        raise HTTPException(status_code=403, detail="Only the requested doctor can decline access")
    relation = db.query(PatientDoctorAccess).filter_by(
        patient_user_id=patient_id, doctor_user_id=doctor_id, status="PENDING").first()
    if relation is None:
        raise HTTPException(status_code=404, detail="Pending access request not found")
    relation.status, relation.revoked_at = "DECLINED", datetime.now(timezone.utc)
    record_audit_event(db, actor_user_id=user.id, action="PATIENT_ACCESS_DECLINED",
                       resource_type="PATIENT_DOCTOR_ACCESS", resource_id=str(relation.id),
                       metadata={"patient_user_id": patient_id})
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="DOCTOR_ACCESS_DECLINED",
                          source_type="PATIENT_DOCTOR_ACCESS", source_id=str(relation.id),
                          summary="Clinician declined patient access")
    db.commit()
    db.refresh(relation)
    return _access_read(db, relation)


@router.get("/{patient_id}/access-requests")
def list_patient_access(patient_id: int, db: Db, user: Current):
    if user.role is not UserRole.PATIENT or user.id != patient_id:
        raise HTTPException(status_code=403, detail="Patients may view only their own access requests")
    rows = db.scalars(select(PatientDoctorAccess).where(
        PatientDoctorAccess.patient_user_id == patient_id).order_by(PatientDoctorAccess.granted_at.desc())).all()
    return [_access_read(db, row) for row in rows]


@router.post("/{patient_id}/doctors/{doctor_id}/access", status_code=201)
def grant_access(patient_id: int, doctor_id: int, db: Db, user: Current):
    if user.role is not UserRole.PATIENT or user.id != patient_id:
        raise HTTPException(status_code=403, detail="Only the patient can grant access")
    from app.auth.models import User as UserModel
    doctor = db.get(UserModel, doctor_id)
    if doctor is None or doctor.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=404, detail="Doctor not found")
    relation = db.query(PatientDoctorAccess).filter_by(patient_user_id=patient_id, doctor_user_id=doctor_id).first()
    if relation is None:
        relation = PatientDoctorAccess(patient_user_id=patient_id, doctor_user_id=doctor_id, status="PENDING")
        db.add(relation)
    elif relation.status != "ACTIVE":
        relation.status, relation.granted_at, relation.revoked_at = "PENDING", datetime.now(timezone.utc), None
    db.flush()
    record_audit_event(db, actor_user_id=user.id, action="PATIENT_ACCESS_REQUESTED", resource_type="PATIENT_DOCTOR_ACCESS", resource_id=str(relation.id), metadata={"doctor_user_id": doctor_id})
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="DOCTOR_ACCESS_REQUESTED",
                          source_type="PATIENT_DOCTOR_ACCESS", source_id=str(relation.id), summary="Patient requested clinician access")
    db.commit()
    return {"patient_id": patient_id, "doctor_id": doctor_id, "status": relation.status}


@router.post("/{patient_id}/doctors/{doctor_id}/revoke")
def revoke_access(patient_id: int, doctor_id: int, db: Db, user: Current):
    if user.role is not UserRole.PATIENT or user.id != patient_id:
        raise HTTPException(status_code=403, detail="Only the patient can revoke access")
    relation = db.query(PatientDoctorAccess).filter_by(patient_user_id=patient_id, doctor_user_id=doctor_id, status="ACTIVE").first()
    if relation is None:
        raise HTTPException(status_code=404, detail="Access grant not found")
    relation.status, relation.revoked_at = "REVOKED", datetime.now(timezone.utc)
    record_audit_event(db, actor_user_id=user.id, action="PATIENT_ACCESS_REVOKED", resource_type="PATIENT_DOCTOR_ACCESS", resource_id=str(relation.id), metadata={"doctor_user_id": doctor_id})
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id, event_type="DOCTOR_ACCESS_REVOKED",
                          source_type="PATIENT_DOCTOR_ACCESS", source_id=str(relation.id), summary="Patient revoked doctor access")
    db.commit()
    return {"patient_id": patient_id, "doctor_id": doctor_id, "status": "REVOKED"}
