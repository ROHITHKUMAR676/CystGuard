from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SymptomCreate(BaseModel):
    symptom_type: str = Field(min_length=1, max_length=64)
    severity: int | None = Field(default=None, ge=0, le=10)
    onset_date: date | None = None
    duration: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["ACTIVE", "RESOLVED", "UNKNOWN"] = "UNKNOWN"


class SymptomPatch(BaseModel):
    symptom_type: str | None = Field(default=None, min_length=1, max_length=64)
    severity: int | None = Field(default=None, ge=0, le=10)
    onset_date: date | None = None
    duration: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["ACTIVE", "RESOLVED", "UNKNOWN"] | None = None
    review_note: str | None = Field(default=None, max_length=2000)


class SymptomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    patient_id: int
    created_by_user_id: int
    symptom_type: str
    severity: int | None
    onset_date: date | None
    recorded_at: datetime
    duration: str | None
    notes: str | None
    status: str
    source: str
    review_status: str
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    review_note: str | None
    updated_at: datetime


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    visibility: Literal["PATIENT_VISIBLE", "CLINICIAN_ONLY"] = "PATIENT_VISIBLE"
    source_context: str = Field(default="CARE_WORKFLOW", min_length=1, max_length=64)


class ReviewCreate(BaseModel):
    item_type: str = Field(min_length=1, max_length=48)
    priority: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL"
    source_type: str | None = Field(default=None, max_length=48)
    source_id: str | None = Field(default=None, max_length=36)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def source_pair(self):
        if (self.source_type is None) != (self.source_id is None):
            raise ValueError("source_type and source_id must be supplied together")
        return self


class ReviewResolve(BaseModel):
    resolution_note: str = Field(min_length=1, max_length=2000)
    status: Literal["RESOLVED", "DISMISSED"] = "RESOLVED"


class MealCreate(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    patient_confirmed: bool = False


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
