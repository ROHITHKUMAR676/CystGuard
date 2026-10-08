from datetime import date, datetime
from enum import Enum
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeasurementCreate(BaseModel):
    feature: str = Field(min_length=1, max_length=64)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=32)
    finding_status: str | None = None
    measured_at: date | None = None
    source: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=32)
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification_status: str = "UNVERIFIED"
    comparability: str = "UNKNOWN"

    @model_validator(mode="after")
    def validate_shape(self):
        if (self.value is None) == (self.finding_status is None):
            raise ValueError("Provide exactly one of numeric value or finding_status")
        if self.value is not None and (self.unit is None or self.value < 0 or not isfinite(self.value)):
            raise ValueError("Numeric measurements require a unit and finite nonnegative value")
        if self.finding_status is not None and self.finding_status not in {"PRESENT", "ABSENT", "UNKNOWN"}:
            raise ValueError("Unsupported finding_status")
        if self.verification_status not in {"UNVERIFIED", "VERIFIED"} or self.comparability not in {"COMPARABLE", "INCOMPARABLE", "UNKNOWN"}:
            raise ValueError("Invalid verification_status or comparability")
        return self


class MeasurementRead(MeasurementCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    created_by_user_id: int
    created_at: datetime


class ChangeDirection(str, Enum):
    UNCHANGED = "UNCHANGED"
    INCREASED = "INCREASED"
    DECREASED = "DECREASED"
    NEW = "NEW"
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class StudyDateRead(BaseModel):
    id: str
    study_date: date | None
    uploaded_at: datetime
    assessments: list[dict]
    measurements: list[MeasurementRead]
