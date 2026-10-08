from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.auth.access import require_patient_doctor
from app.config import Settings, get_settings
from app.database import get_db
from app.ocr.document_service import create_ocr_document
from app.ocr.models import (
    ConflictReviewStatus, MedicationConflict, MedicationLifecycleStatus, MedicationRecord,
    OCRDocument, OCRDocumentType, OCRVerificationStatus,
)
from app.ocr.provider import OCRProvider, get_ocr_provider
from app.schemas.medication import (
    ConflictReview, MedicationConflictRead, MedicationOCRRead, MedicationRecordRead,
    MedicationStatus, MedicationVerification,
)
from app.schemas.report import DocumentRead, DocumentType
from app.services.audit_service import record_audit_event
from app.services.careloop_service import record_careloop_event
from app.storage.service import StorageBackend, get_storage

router = APIRouter(tags=["Medication OCR"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _owned_document(db: Session, document_id: str, owner_id: int) -> OCRDocument:
    doc = db.scalar(select(OCRDocument).where(
        OCRDocument.id == document_id, OCRDocument.owner_user_id == owner_id,
        OCRDocument.document_type == OCRDocumentType.MEDICATION,
    ))
    if doc is None:
        raise HTTPException(status_code=404, detail="Medication document not found.")
    return doc


def _record_read(db: Session, record: MedicationRecord) -> MedicationRecordRead:
    conflicts = db.scalars(select(MedicationConflict).where(
        MedicationConflict.owner_user_id == record.owner_user_id,
        (MedicationConflict.left_record_id == record.id) | (MedicationConflict.right_record_id == record.id),
    )).all()
    return MedicationRecordRead(
        id=record.id, patient_id=record.patient_id, source_document_id=record.document_id,
        source_type="OCR_EXTRACTED", extracted_fields=record.extracted_fields,
        verified_fields=record.verified_fields, verification_status=record.verification_status,
        medication_status=record.medication_status, extraction_confidence=record.extracted_fields.get("extraction_confidence"),
        page=record.extracted_fields.get("page"), source_text=record.extracted_fields.get("source_text"),
        doctor_note=record.doctor_note, created_at=record.created_at, verified_at=record.verified_at,
        conflicts=tuple(MedicationConflictRead(
            id=c.id, medication_record_ids=(c.left_record_id, c.right_record_id),
            conflicting_fields=c.conflicting_fields, status=c.status,
            resolution_record_id=c.resolution_record_id,
            created_at=c.created_at, reviewed_at=c.reviewed_at, review_note=c.review_note,
        ) for c in conflicts),
    )


def _read_document(db: Session, document: OCRDocument) -> MedicationOCRRead:
    records = db.scalars(select(MedicationRecord).where(MedicationRecord.document_id == document.id).order_by(MedicationRecord.created_at)).all()
    return MedicationOCRRead(document=DocumentRead.model_validate(document, from_attributes=True),
                              medications=tuple(_record_read(db, record) for record in records))


@router.post("/medications/documents", response_model=MedicationOCRRead, status_code=status.HTTP_201_CREATED)
def upload_medication_document(
    upload: Annotated[UploadFile, File()], db: Db, current_user: CurrentUser,
    storage: Annotated[StorageBackend, Depends(get_storage)],
    provider: Annotated[OCRProvider, Depends(get_ocr_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MedicationOCRRead:
    document, _, _ = create_ocr_document(
        upload, document_type=DocumentType.MEDICATION, owner=current_user, db=db,
        storage=storage, provider=provider, settings=settings,
    )
    return _read_document(db, document)


@router.get("/medications/ocr/{job_id}", response_model=MedicationOCRRead)
def read_medication_ocr(job_id: str, db: Db, current_user: CurrentUser) -> MedicationOCRRead:
    return _read_document(db, _owned_document(db, job_id, current_user.id))


@router.post("/medications/{medication_id}/verify", response_model=MedicationRecordRead)
def verify_medication(
    medication_id: str, payload: MedicationVerification, db: Db, current_user: CurrentUser,
) -> MedicationRecordRead:
    if current_user.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Doctor verification is required.")
    record = db.get(MedicationRecord, medication_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Medication record not found.")
    if record.owner_user_id != current_user.id and record.patient_id is None:
        raise HTTPException(status_code=404, detail="Medication record not found.")
    if record.patient_id is not None:
        require_patient_doctor(db, current_user, record.patient_id)
    elif record.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Medication record not found.")
    record.verified_fields = {**(record.extracted_fields or {}), **payload.fields}
    record.verification_status = OCRVerificationStatus.VERIFIED
    record.verified_by_user_id = current_user.id
    record.verified_at = datetime.now(timezone.utc)
    if payload.medication_status is not None:
        record.medication_status = MedicationLifecycleStatus(payload.medication_status.value)
    record.doctor_note = payload.doctor_note
    outstanding = db.scalar(select(MedicationRecord.id).where(
        MedicationRecord.document_id == record.document_id,
        MedicationRecord.id != record.id,
        MedicationRecord.verification_status == OCRVerificationStatus.UNVERIFIED,
    ).limit(1))
    if outstanding is None:
        record.document.verification_status = OCRVerificationStatus.VERIFIED
        record.document.verified_by_user_id = current_user.id
        record.document.verified_at = record.verified_at
        record.document.verification_note = payload.doctor_note
    record_audit_event(db, actor_user_id=current_user.id, action="MEDICATION_OCR_VERIFIED",
                       resource_type="MEDICATION_RECORD", resource_id=record.id,
                       metadata={"field_count": len(payload.fields), "lifecycle_status_set": payload.medication_status is not None})
    if record.patient_id is not None:
        record_careloop_event(db, patient_id=record.patient_id, actor_user_id=current_user.id,
                              event_type="MEDICATION_VERIFIED", source_type="MEDICATION_RECORD",
                              source_id=record.id, summary="Medication record verified by clinician")
    db.commit()
    db.refresh(record)
    return _record_read(db, record)


@router.get("/patients/{patient_id}/medications", response_model=tuple[MedicationRecordRead, ...])
def list_patient_medications(patient_id: int, db: Db, current_user: CurrentUser) -> tuple[MedicationRecordRead, ...]:
    if current_user.role is UserRole.PATIENT:
        if current_user.id != patient_id:
            raise HTTPException(status_code=403, detail="Patient medication access is not authorized.")
    else:
        require_patient_doctor(db, current_user, patient_id)
    records = db.scalars(select(MedicationRecord).where(
        MedicationRecord.patient_id == patient_id,
    ).order_by(MedicationRecord.created_at.desc())).all()
    return tuple(_record_read(db, record) for record in records)


@router.post("/patients/{patient_id}/medications/{medication_id}/review-conflict", response_model=MedicationConflictRead)
def review_medication_conflict(
    patient_id: int, medication_id: str, payload: ConflictReview, db: Db, current_user: CurrentUser,
) -> MedicationConflictRead:
    if current_user.role is not UserRole.PATIENT or current_user.id != patient_id:
        raise HTTPException(status_code=403, detail="Patient medication access is not authorized.")
    record = db.scalar(select(MedicationRecord).where(
        MedicationRecord.id == medication_id, MedicationRecord.owner_user_id == current_user.id,
        MedicationRecord.patient_id == patient_id,
    ))
    if record is None:
        raise HTTPException(status_code=404, detail="Medication record not found.")
    conflict = db.scalar(select(MedicationConflict).where(
        MedicationConflict.owner_user_id == current_user.id,
        MedicationConflict.status == ConflictReviewStatus.CONFLICT_REQUIRES_REVIEW,
        (MedicationConflict.left_record_id == record.id) | (MedicationConflict.right_record_id == record.id),
    ).order_by(MedicationConflict.created_at.desc()))
    if conflict is None:
        raise HTTPException(status_code=404, detail="Unresolved medication conflict not found.")
    if payload.resolution_record_id not in {conflict.left_record_id, conflict.right_record_id}:
        raise HTTPException(status_code=422, detail="Resolution must identify one of the conflicting source records.")
    conflict.status = ConflictReviewStatus.REVIEWED
    conflict.resolution_record_id = payload.resolution_record_id
    conflict.reviewed_by_user_id = current_user.id
    conflict.reviewed_at = datetime.now(timezone.utc)
    conflict.review_note = payload.review_note
    record_audit_event(db, actor_user_id=current_user.id, action="MEDICATION_CONFLICT_REVIEWED",
                       resource_type="MEDICATION_CONFLICT", resource_id=conflict.id,
                       metadata={"record_id": record.id})
    db.commit()
    db.refresh(conflict)
    return MedicationConflictRead(
        id=conflict.id, medication_record_ids=(conflict.left_record_id, conflict.right_record_id),
        conflicting_fields=conflict.conflicting_fields, status=conflict.status,
        resolution_record_id=conflict.resolution_record_id,
        created_at=conflict.created_at, reviewed_at=conflict.reviewed_at, review_note=conflict.review_note,
    )
