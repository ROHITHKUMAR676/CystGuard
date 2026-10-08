from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.access import require_patient_access
from app.auth.models import User, UserRole
from app.audit.models import AuditEvent
from app.config import Settings, get_settings
from app.database import get_db
from app.ocr.document_service import create_ocr_document
from app.ocr.models import MedicalReport, OCRDocument, OCRDocumentType, OCRVerificationStatus
from app.ocr.provider import OCRProvider, get_ocr_provider
from app.schemas.report import DocumentRead, DocumentType, ExtractedField, MedicalReportRead, ReportVerification
from app.services.audit_service import record_audit_event
from app.storage.service import StorageBackend, get_storage

router = APIRouter(prefix="/reports", tags=["Medical reports"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _accessible_report(db: Session, report_id: str, user: User) -> tuple[OCRDocument, MedicalReport]:
    row = db.execute(select(OCRDocument, MedicalReport).join(
        MedicalReport, MedicalReport.document_id == OCRDocument.id).where(
            or_(MedicalReport.id == report_id, OCRDocument.id == report_id),
            OCRDocument.document_type == OCRDocumentType.REPORT,
        )).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Medical report not found.")
    document, report = row
    if document.owner_user_id != user.id:
        if user.role is not UserRole.DOCTOR:
            raise HTTPException(status_code=404, detail="Medical report not found.")
        require_patient_access(db, user, document.owner_user_id)
    return document, report


def _read_report(document: OCRDocument, report: MedicalReport) -> MedicalReportRead:
    return MedicalReportRead(
        id=report.id,
        document=DocumentRead.model_validate(document, from_attributes=True),
        fields={key: ExtractedField.model_validate(value) for key, value in report.extracted_fields.items()},
        verified_fields=report.verified_fields,
        doctor_note=report.doctor_note,
    )


@router.post("/documents", response_model=MedicalReportRead, status_code=status.HTTP_201_CREATED)
def upload_report_document(
    upload: Annotated[UploadFile, File()], db: Db, current_user: CurrentUser,
    storage: Annotated[StorageBackend, Depends(get_storage)],
    provider: Annotated[OCRProvider, Depends(get_ocr_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MedicalReportRead:
    document, report, _ = create_ocr_document(
        upload, document_type=DocumentType.REPORT, owner=current_user, db=db,
        storage=storage, provider=provider, settings=settings,
    )
    return _read_report(document, report)


@router.get("", response_model=list[MedicalReportRead])
def list_owned_reports(db: Db, current_user: CurrentUser) -> list[MedicalReportRead]:
    rows = db.execute(select(OCRDocument, MedicalReport).join(
        MedicalReport, MedicalReport.document_id == OCRDocument.id).where(
            OCRDocument.owner_user_id == current_user.id,
            OCRDocument.document_type == OCRDocumentType.REPORT,
        ).order_by(OCRDocument.created_at.desc())).all()
    return [_read_report(document, report) for document, report in rows]


@router.get("/patients/{patient_id}", response_model=list[MedicalReportRead])
def list_patient_reports(patient_id: int, db: Db, current_user: CurrentUser) -> list[MedicalReportRead]:
    require_patient_access(db, current_user, patient_id)
    rows = db.execute(select(OCRDocument, MedicalReport).join(
        MedicalReport, MedicalReport.document_id == OCRDocument.id).where(
            OCRDocument.owner_user_id == patient_id,
            OCRDocument.document_type == OCRDocumentType.REPORT,
        ).order_by(OCRDocument.created_at.desc())).all()
    return [_read_report(document, report) for document, report in rows]


@router.get("/ocr/{report_id}", response_model=MedicalReportRead)
@router.get("/{report_id}", response_model=MedicalReportRead)
def read_report(report_id: str, db: Db, current_user: CurrentUser) -> MedicalReportRead:
    document, report = _accessible_report(db, report_id, current_user)
    return _read_report(document, report)


@router.post("/{report_id}/verify", response_model=MedicalReportRead)
def verify_report(
    report_id: str, payload: ReportVerification, db: Db, current_user: CurrentUser,
) -> MedicalReportRead:
    if current_user.role is not UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Doctor verification is required.")
    document, report = _accessible_report(db, report_id, current_user)
    document.verification_status = OCRVerificationStatus.VERIFIED
    document.verified_by_user_id = current_user.id
    document.verified_at = datetime.now(timezone.utc)
    document.verification_note = payload.doctor_note
    report.verified_fields = payload.fields
    report.doctor_note = payload.doctor_note
    record_audit_event(db, actor_user_id=current_user.id, action="REPORT_OCR_VERIFIED",
                       resource_type="MEDICAL_REPORT", resource_id=report.id,
                       metadata={"field_count": len(payload.fields)})
    db.commit()
    db.refresh(document)
    db.refresh(report)
    return _read_report(document, report)
