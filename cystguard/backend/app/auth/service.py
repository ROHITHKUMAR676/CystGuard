import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import PatientDoctorAccess, User, UserRole
from app.schemas import auth as auth_schemas
from app.auth.security import create_access_token, hash_password, verify_password


def register_user(payload: auth_schemas.UserRegister, db: Session) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    doctor = None
    if payload.role is UserRole.PATIENT and payload.doctor_access_code:
        doctor = db.scalar(select(User).where(User.access_code == payload.doctor_access_code.strip().upper(),
                                               User.role == UserRole.DOCTOR))
        if doctor is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="Clinician access code was not found")
    code = None
    if payload.role is UserRole.DOCTOR:
        while code is None:
            candidate = f"CG-{secrets.token_hex(3).upper()}"
            if db.scalar(select(User.id).where(User.access_code == candidate)) is None:
                code = candidate
    user = User(email=payload.email, display_name=payload.display_name,
                access_code=code, hashed_password=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.flush()
        if doctor is not None:
            db.add(PatientDoctorAccess(patient_user_id=user.id, doctor_user_id=doctor.id, status="PENDING"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from exc
    db.refresh(user)
    return user


def authenticate_user(payload: auth_schemas.LoginRequest, db: Session) -> tuple[User, str, int]:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        token, lifetime = create_access_token(str(user.id))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc
    return user, token, lifetime
