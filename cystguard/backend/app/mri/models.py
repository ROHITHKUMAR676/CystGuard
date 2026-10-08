from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.database import Base


class MRIStudyStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    ANALYZED = "ANALYZED"
    FAILED = "FAILED"


class MRIFileFormat(str, Enum):
    NIFTI = "NIFTI"
    NIFTI_GZ = "NIFTI_GZ"


class PredictionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class InputQualityStatus(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class MRIStudy(Base):
    __tablename__ = "mri_studies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    modality: Mapped[str] = mapped_column(String(16), nullable=False, default="T1")
    file_format: Mapped[MRIFileFormat] = mapped_column(SqlEnum(MRIFileFormat, native_enum=False), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    patient_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    study_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[MRIStudyStatus] = mapped_column(
        SqlEnum(MRIStudyStatus, native_enum=False), default=MRIStudyStatus.UPLOADED, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    owner: Mapped[User] = relationship(User, foreign_keys=[owner_user_id])
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="study", cascade="all, delete-orphan", order_by="Assessment.created_at"
    )
    measurements: Mapped[list["StudyMeasurement"]] = relationship(back_populates="study", cascade="all, delete-orphan")


class StudyMeasurement(Base):
    __tablename__ = "study_measurements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    study_id: Mapped[str] = mapped_column(ForeignKey("mri_studies.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    feature: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    finding_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    measured_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNVERIFIED")
    comparability: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    study: Mapped[MRIStudy] = relationship(back_populates="measurements")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    mri_study_id: Mapped[str] = mapped_column(
        ForeignKey("mri_studies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    architecture: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_status: Mapped[PredictionStatus] = mapped_column(
        SqlEnum(PredictionStatus, native_enum=False), nullable=False
    )
    input_quality_status: Mapped[InputQualityStatus] = mapped_column(
        SqlEnum(InputQualityStatus, native_enum=False), nullable=False
    )
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    clinical_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    guideline_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trust_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    study: Mapped[MRIStudy] = relationship(back_populates="assessments")
