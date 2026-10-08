from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.report import DocumentRead, VerificationStatus


class MedicationStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"
    HISTORICAL = "HISTORICAL"
    ENDED = "ENDED"
    DISCONTINUED = "DISCONTINUED"


class ConflictStatus(str, Enum):
    CONFLICT_REQUIRES_REVIEW = "CONFLICT_REQUIRES_REVIEW"
    REVIEWED = "REVIEWED"


class MedicationVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, str | None] = Field(default_factory=dict)
    medication_status: MedicationStatus | None = None
    doctor_note: str | None = Field(default=None, max_length=2000)

    @field_validator("fields")
    @classmethod
    def known_medication_fields_only(cls, value):
        allowed = {"name", "generic_name", "brand_name", "strength", "normalized_strength", "dose", "dosage_form", "frequency", "normalized_frequency", "route", "normalized_route", "start_date", "end_date", "duration", "prescriber", "indication"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unsupported medication fields: {', '.join(sorted(unknown))}")
        return value


class ConflictReview(BaseModel):
    review_note: str = Field(min_length=1, max_length=2000)
    resolution_record_id: str


class MedicationConflictRead(BaseModel):
    id: str
    medication_record_ids: tuple[str, str]
    conflicting_fields: dict[str, tuple[Any, Any]]
    status: ConflictStatus
    resolution_record_id: str | None = None
    created_at: datetime
    reviewed_at: datetime | None
    review_note: str | None


class MedicationRecordRead(BaseModel):
    id: str
    patient_id: int | None
    source_document_id: str
    source_type: str
    extracted_fields: dict[str, Any]
    verified_fields: dict[str, Any] | None
    verification_status: VerificationStatus
    medication_status: MedicationStatus
    extraction_confidence: float | None
    page: int | None
    source_text: str | None
    doctor_note: str | None
    created_at: datetime
    verified_at: datetime | None
    conflicts: tuple[MedicationConflictRead, ...] = ()


class MedicationOCRRead(BaseModel):
    document: DocumentRead
    medications: tuple[MedicationRecordRead, ...]
