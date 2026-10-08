from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SurveillanceCreate(BaseModel):
    target_follow_up_date: date
    interval: int | None = Field(default=None, gt=0)
    interval_unit: str | None = None
    reason: str = Field(min_length=1)
    notes: str | None = None
    next_review_date: date | None = None

    @model_validator(mode="after")
    def interval_pair(self):
        if (self.interval is None) != (self.interval_unit is None):
            raise ValueError("interval and interval_unit must be supplied together")
        if self.interval_unit is not None and self.interval_unit not in {"DAYS", "WEEKS", "MONTHS", "YEARS"}:
            raise ValueError("Unsupported interval_unit")
        return self


class SurveillanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    patient_user_id: int
    created_by_user_id: int
    target_follow_up_date: date
    interval: int | None
    interval_unit: str | None
    reason: str
    status: str
    notes: str | None
    last_reviewed_at: datetime | None
    next_review_date: date | None
    created_at: datetime


class EventCreate(BaseModel):
    event_type: str
    planned_date: date
    notes: str | None = None

    @model_validator(mode="after")
    def event_type_valid(self):
        if self.event_type not in {"MRI_FOLLOW_UP", "SPECIALIST_REVIEW", "EUS_REVIEW", "CLINIC_VISIT", "OTHER"}:
            raise ValueError("Unsupported event_type")
        return self
