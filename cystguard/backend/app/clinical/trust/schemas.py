from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TrustSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AIRiskClass(str, Enum):
    HIGH_RISK = "HIGH_RISK"
    NO_LOW_RISK = "NO_LOW_RISK"


class AIOutput(TrustSchema):
    """Cyst-X metadata and raw decision output; raw_score is not a probability."""

    model_id: str = Field(min_length=1, max_length=64)
    model_version: str = Field(min_length=1, max_length=128)
    risk_class: AIRiskClass | None
    raw_score: float | None = Field(default=None, allow_inf_nan=False, ge=0, le=1)
    threshold: float | None = Field(default=None, allow_inf_nan=False, ge=0, le=1)

    @model_validator(mode="after")
    def score_and_threshold_are_paired(self):
        if (self.raw_score is None) != (self.threshold is None):
            raise ValueError("raw_score and threshold must either both be provided or both be absent")
        if self.risk_class is None and self.raw_score is not None:
            raise ValueError("An unavailable AI classification cannot include score/threshold")
        return self


class TrustStatus(str, Enum):
    CONCORDANT_HIGH = "CONCORDANT_HIGH"
    CONCORDANT_LOWER = "CONCORDANT_LOWER"
    DISCORDANT = "DISCORDANT"
    REVIEW = "REVIEW"
    INDETERMINATE = "INDETERMINATE"


class KyotoEvidenceStatus(str, Enum):
    HIGH_RISK_EVIDENCE = "HIGH_RISK_EVIDENCE"
    WORRISOME_EVIDENCE = "WORRISOME_EVIDENCE"
    LOWER_RISK_EVIDENCE = "LOWER_RISK_EVIDENCE"
    INDETERMINATE = "INDETERMINATE"


class UncertaintyStatus(str, Enum):
    NOT_CALIBRATED = "NOT_CALIBRATED"
    UNAVAILABLE = "UNAVAILABLE"


class CalibrationStatus(str, Enum):
    NOT_CALIBRATED = "NOT_CALIBRATED"
    CALIBRATED = "CALIBRATED"


class CalibrationResult(TrustSchema):
    available: bool = False
    method: str | None = None
    model_version: str
    calibration_dataset: str | None = None
    calibrated_score: float | None = Field(default=None, allow_inf_nan=False, ge=0, le=1)
    status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED

    @model_validator(mode="after")
    def calibration_metadata_is_consistent(self):
        complete = bool(self.method and self.calibration_dataset and self.model_version and self.calibrated_score is not None)
        if self.available and (not complete or self.status is not CalibrationStatus.CALIBRATED):
            raise ValueError("Available calibration requires method, dataset, model version, score, and CALIBRATED status")
        if not self.available and (self.calibrated_score is not None or self.status is CalibrationStatus.CALIBRATED):
            raise ValueError("Unavailable calibration cannot contain a calibrated score")
        return self


class AITrustView(TrustSchema):
    model_id: str
    model_version: str
    risk_class: AIRiskClass | None
    raw_score: float | None
    threshold: float | None
    decision_margin: float | None
    decision_margin_label: str = "DECISION_MARGIN"


class KyotoTrustView(TrustSchema):
    hrs_present: tuple[str, ...]
    wf_present: tuple[str, ...]
    status: KyotoEvidenceStatus
    missing_data: tuple[str, ...]
    not_evaluable_rules: tuple[str, ...]
    guideline_id: str
    guideline_version: str


class ConcordanceView(TrustSchema):
    status: TrustStatus
    reason_codes: tuple[str, ...]


class UncertaintyView(TrustSchema):
    status: UncertaintyStatus
    reason_codes: tuple[str, ...]


class TrustEngineVersion(TrustSchema):
    name: str
    version: str


class TrustResult(TrustSchema):
    trust_status: TrustStatus
    ai: AITrustView
    kyoto: KyotoTrustView
    concordance: ConcordanceView
    uncertainty: UncertaintyView
    calibration: CalibrationResult
    trust_engine: TrustEngineVersion
    evaluated_at: datetime
    doctor_review_required: bool

    @field_validator("evaluated_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must include a timezone")
        return value
