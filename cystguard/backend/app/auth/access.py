from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.models import PatientDoctorAccess, User, UserRole


def require_patient_access(db: Session, user: User, patient_id: int) -> None:
    if user.role is UserRole.PATIENT and user.id == patient_id:
        return
    if user.role is UserRole.DOCTOR:
        granted = db.query(PatientDoctorAccess.id).filter_by(
            patient_user_id=patient_id, doctor_user_id=user.id, status="ACTIVE"
        ).first()
        if granted:
            return
    raise HTTPException(status_code=404, detail="Patient not found")


def require_patient_doctor(db: Session, user: User, patient_id: int) -> None:
    if user.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Doctor access is required")
    require_patient_access(db, user, patient_id)
