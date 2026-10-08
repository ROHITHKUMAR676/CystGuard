from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.database import Base


class OCRDocumentType(str, Enum):
    REPORT = "REPORT"
    MEDICATION = "MEDICATION"


class OCRExtractionStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class OCRVerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"


class MedicationLifecycleStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"
    HISTORICAL = "HISTORICAL"
    ENDED = "ENDED"
    DISCONTINUED = "DISCONTINUED"


class ConflictReviewStatus(str, Enum):
    CONFLICT_REQUIRES_REVIEW = "CONFLICT_REQUIRES_REVIEW"
    REVIEWED = "REVIEWED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OCRDocument(Base):
    __tablename__ = "ocr_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    document_type: Mapped[OCRDocumentType] = mapped_column(SqlEnum(OCRDocumentType, native_enum=False), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    extraction_status: Mapped[OCRExtractionStatus] = mapped_column(SqlEnum(OCRExtractionStatus, native_enum=False), nullable=False)
    verification_status: Mapped[OCRVerificationStatus] = mapped_column(SqlEnum(OCRVerificationStatus, native_enum=False), nullable=False, default=OCRVerificationStatus.UNVERIFIED)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    owner: Mapped[User] = relationship(foreign_keys=[owner_user_id])
    verified_by: Mapped[User | None] = relationship(foreign_keys=[verified_by_user_id])
    report: Mapped["MedicalReport | None"] = relationship(back_populates="document", cascade="all, delete-orphan", uselist=False)
    medications: Mapped[list["MedicationRecord"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class MedicalReport(Base):
    __tablename__ = "medical_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("ocr_documents.id", ondelete="CASCADE"), unique=True, nullable=False)
    extracted_fields: Mapped[dict] = mapped_column(JSON, nullable=False)
    verified_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    doctor_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[OCRDocument] = relationship(back_populates="report")


class MedicationRecord(Base):
    __tablename__ = "medication_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("ocr_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    extracted_fields: Mapped[dict] = mapped_column(JSON, nullable=False)
    verified_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verification_status: Mapped[OCRVerificationStatus] = mapped_column(SqlEnum(OCRVerificationStatus, native_enum=False), nullable=False, default=OCRVerificationStatus.UNVERIFIED)
    medication_status: Mapped[MedicationLifecycleStatus] = mapped_column(SqlEnum(MedicationLifecycleStatus, native_enum=False), nullable=False, default=MedicationLifecycleStatus.UNKNOWN)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    doctor_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[OCRDocument] = relationship(back_populates="medications")
    owner: Mapped[User] = relationship(foreign_keys=[owner_user_id])
    conflicts_as_left: Mapped[list["MedicationConflict"]] = relationship(foreign_keys="MedicationConflict.left_record_id", cascade="all, delete-orphan")
    conflicts_as_right: Mapped[list["MedicationConflict"]] = relationship(foreign_keys="MedicationConflict.right_record_id", cascade="all, delete-orphan")


class MedicationConflict(Base):
    __tablename__ = "medication_conflicts"
    __table_args__ = (Index("ix_medication_conflict_owner_status", "owner_user_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    left_record_id: Mapped[str] = mapped_column(ForeignKey("medication_records.id", ondelete="CASCADE"), nullable=False)
    right_record_id: Mapped[str] = mapped_column(ForeignKey("medication_records.id", ondelete="CASCADE"), nullable=False)
    conflicting_fields: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[ConflictReviewStatus] = mapped_column(SqlEnum(ConflictReviewStatus, native_enum=False), nullable=False, default=ConflictReviewStatus.CONFLICT_REQUIRES_REVIEW)
    resolution_record_id: Mapped[str | None] = mapped_column(ForeignKey("medication_records.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    left_record: Mapped[MedicationRecord] = relationship(foreign_keys=[left_record_id], back_populates="conflicts_as_left")
    right_record: Mapped[MedicationRecord] = relationship(foreign_keys=[right_record_id], back_populates="conflicts_as_right")
