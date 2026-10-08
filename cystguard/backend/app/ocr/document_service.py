from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.config import Settings, get_settings
from app.ocr.medication_ocr_service import extract_medication_candidates, normalized_medication_key
from app.ocr.models import (
    ConflictReviewStatus, MedicationConflict, MedicationLifecycleStatus, MedicationRecord,
    OCRDocument, OCRDocumentType, OCRExtractionStatus, OCRVerificationStatus,
)
from app.ocr.normalizer import normalize_whitespace
from app.ocr.provider import OCRProvider, OCRProviderError
from app.ocr.report_ocr_service import extract_report_fields
from app.ocr.verifier import find_medication_conflicts
from app.schemas.report import DocumentType
from app.storage.service import StorageBackend


_FILE_TYPES = {
    ".pdf": ("application/pdf", lambda b: b.startswith(b"%PDF-")),
    ".png": ("image/png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ".tif": ("image/tiff", lambda b: b.startswith((b"II*\x00", b"MM\x00*"))),
    ".tiff": ("image/tiff", lambda b: b.startswith((b"II*\x00", b"MM\x00*"))),
    ".bmp": ("image/bmp", lambda b: b.startswith(b"BM")),
}


def _read_and_validate_upload(upload: UploadFile, max_size: int) -> tuple[bytes, str, str]:
    filename = (upload.filename or "").replace("\\", "/").split("/")[-1]
    if not filename or "\x00" in filename or len(filename) > 255:
        raise HTTPException(status_code=400, detail="A valid document filename is required.")
    suffix = Path(filename).suffix.lower()
    if suffix not in _FILE_TYPES:
        raise HTTPException(status_code=415, detail="Supported documents are PDF, PNG, JPEG, TIFF, and BMP.")
    content = upload.file.read(max_size + 1)
    upload.file.seek(0)
    if not content:
        raise HTTPException(status_code=422, detail="Document is empty.")
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="Document exceeds the configured upload limit.")
    media_type, signature_check = _FILE_TYPES[suffix]
    if not signature_check(content):
        raise HTTPException(status_code=422, detail="Document extension and file contents do not match.")
    return content, filename, media_type


def _make_conflicts(db: Session, owner: User, records: list[MedicationRecord]) -> None:
    if owner.role is not UserRole.PATIENT:
        return
    existing = db.scalars(select(MedicationRecord).where(
        MedicationRecord.patient_id == owner.id,
        MedicationRecord.owner_user_id == owner.id,
        MedicationRecord.id.not_in([row.id for row in records]),
    )).all()
    all_records = [*existing, *records]
    data_by_id = {row.id: row.extracted_fields for row in all_records}
    for pair in find_medication_conflicts([data_by_id[row.id] for row in all_records]):
        left_data, right_data = pair["left"], pair["right"]
        left_id = next(row.id for row in all_records if data_by_id[row.id] is left_data)
        right_id = next(row.id for row in all_records if data_by_id[row.id] is right_data)
        if left_id == right_id:
            continue
        exists = db.scalar(select(MedicationConflict.id).where(
            ((MedicationConflict.left_record_id == left_id) & (MedicationConflict.right_record_id == right_id))
            | ((MedicationConflict.left_record_id == right_id) & (MedicationConflict.right_record_id == left_id)),
            MedicationConflict.status == ConflictReviewStatus.CONFLICT_REQUIRES_REVIEW,
        ))
        if exists:
            continue
        db.add(MedicationConflict(
            owner_user_id=owner.id, left_record_id=left_id, right_record_id=right_id,
            conflicting_fields={key: list(value) for key, value in pair["conflicting_fields"].items()},
            status=ConflictReviewStatus.CONFLICT_REQUIRES_REVIEW,
        ))


def create_ocr_document(
    upload: UploadFile,
    *,
    document_type: DocumentType,
    owner: User,
    db: Session,
    storage: StorageBackend,
    provider: OCRProvider,
    settings: Settings | None = None,
) -> tuple[OCRDocument, object | None, list[MedicationRecord]]:
    settings = settings or get_settings()
    max_size = settings.max_document_upload_size_mb * 1024 * 1024
    content, filename, media_type = _read_and_validate_upload(upload, max_size)
    try:
        ocr = provider.extract(content, media_type)
    except OCRProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if not ocr.pages:
        raise HTTPException(status_code=422, detail="OCR provider returned no pages.")

    document_id = str(uuid4())
    storage_object = storage.store(BytesIO(content), filename, media_type)
    doc = OCRDocument(
        id=document_id,
        owner_user_id=owner.id,
        document_type=OCRDocumentType(document_type.value),
        original_filename=storage_object.original_filename,
        content_type=media_type,
        storage_key=storage_object.key,
        extraction_status=OCRExtractionStatus.EXTRACTED,
        verification_status=OCRVerificationStatus.UNVERIFIED,
        extraction_method=ocr.method,
        page_count=len(ocr.pages),
        extraction_confidence=ocr.extraction_confidence,
        raw_text=ocr.text,
        normalized_text=normalize_whitespace(ocr.text),
    )
    report = None
    medications: list[MedicationRecord] = []
    try:
        db.add(doc)
        if document_type is DocumentType.REPORT:
            fields = extract_report_fields(ocr, document_id)
            from app.ocr.models import MedicalReport
            report = MedicalReport(document_id=document_id, extracted_fields=fields)
            db.add(report)
        else:
            for candidate in extract_medication_candidates(ocr, document_id):
                medications.append(MedicationRecord(
                    id=str(uuid4()), document_id=document_id, owner_user_id=owner.id,
                    patient_id=owner.id if owner.role is UserRole.PATIENT else None,
                    extracted_fields=candidate, verification_status=OCRVerificationStatus.UNVERIFIED,
                    medication_status=MedicationLifecycleStatus.UNKNOWN,
                ))
            db.add_all(medications)
            _make_conflicts(db, owner, medications)
        db.commit()
        db.refresh(doc)
        if report is not None:
            db.refresh(report)
        for row in medications:
            db.refresh(row)
        return doc, report, medications
    except Exception:
        db.rollback()
        storage.delete(storage_object.key)
        raise
