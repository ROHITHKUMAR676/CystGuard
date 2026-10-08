from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentType(str, Enum):
    REPORT = "REPORT"
    MEDICATION = "MEDICATION"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"


class ExtractionStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class FieldStatus(str, Enum):
    PRESENT = "PRESENT"
    UNKNOWN = "UNKNOWN"


class FieldProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    source_type: DocumentType
    page: int | None = Field(default=None, ge=1)
    source_text: str | None = None
    extraction_method: str
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | float | bool | None = None
    normalized_value: str | float | bool | None = None
    status: FieldStatus
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: FieldProvenance | None = None
    needs_verification: bool = True
    normalization_notes: tuple[str, ...] = ()


class DocumentRead(BaseModel):
    id: str
    document_type: DocumentType
    original_filename: str
    content_type: str
    extraction_status: ExtractionStatus
    verification_status: VerificationStatus
    extraction_method: str
    page_count: int
    extraction_confidence: float | None
    raw_text: str
    normalized_text: str
    created_at: datetime
    extracted_at: datetime
    verified_at: datetime | None


class MedicalReportRead(BaseModel):
    id: str
    document: DocumentRead
    fields: dict[str, ExtractedField]
    verified_fields: dict[str, Any] | None = None
    doctor_note: str | None = None


class ReportVerification(BaseModel):
    fields: dict[str, str | float | bool | None] = Field(default_factory=dict)
    doctor_note: str | None = Field(default=None, max_length=2000)

    @field_validator("fields")
    @classmethod
    def known_report_fields_only(cls, value):
        allowed = {"report_type", "patient_name", "patient_identifier", "report_date", "study_date", "modality", "body_region", "findings", "impression", "cyst_size_mm", "cyst_location", "mpd_mm", "mural_nodule_mention", "solid_component_mention", "cyst_wall_characteristics", "ductal_findings", "other_findings"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unsupported report fields: {', '.join(sorted(unknown))}")
        return value
