from datetime import date, datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceSourceType(str, Enum):
    MRI_REPORT = "MRI_REPORT"
    CT_REPORT = "CT_REPORT"
    EUS_REPORT = "EUS_REPORT"
    CE_EUS_REPORT = "CE_EUS_REPORT"
    CYTOLOGY = "CYTOLOGY"
    LAB = "LAB"
    CLINICAL_HISTORY = "CLINICAL_HISTORY"
    LONGITUDINAL_MEASUREMENT = "LONGITUDINAL_MEASUREMENT"


class EvidenceSource(StrictSchema):
    source_type: EvidenceSourceType
    source_id: str = Field(min_length=1, max_length=256)
    page: int | None = Field(default=None, ge=1)
    field: str | None = Field(default=None, max_length=256)
    timestamp: datetime | None = None
    evidence_reference: str | None = Field(default=None, max_length=2048)
    verification_status: str = Field(default="UNVERIFIED", max_length=32)


class FindingStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class Fact(StrictSchema):
    status: FindingStatus = FindingStatus.UNKNOWN
    evidence: tuple[EvidenceSource, ...] = ()


T = TypeVar("T")


class CodedFact(StrictSchema, Generic[T]):
    status: FindingStatus = FindingStatus.UNKNOWN
    value: T | None = None
    evidence: tuple[EvidenceSource, ...] = ()

    @model_validator(mode="after")
    def value_matches_status(self):
        if self.status is FindingStatus.PRESENT and self.value is None:
            raise ValueError("A PRESENT coded finding requires a value")
        if self.status is not FindingStatus.PRESENT and self.value is not None:
            raise ValueError("Only a PRESENT coded finding may include a value")
        return self


class LesionLocation(str, Enum):
    HEAD = "HEAD"
    BODY = "BODY"
    TAIL = "TAIL"
    UNCINATE = "UNCINATE"
    OTHER = "OTHER"


class Measurement(StrictSchema):
    status: FindingStatus = FindingStatus.UNKNOWN
    value_mm: float | None = Field(default=None, allow_inf_nan=False)
    unit: str = "mm"
    measured_at: date | None = None
    measurement_method: str | None = Field(default=None, max_length=128)
    source: str | None = Field(default=None, max_length=256)
    verification_status: str = Field(default="UNVERIFIED", max_length=32)
    evidence: tuple[EvidenceSource, ...] = ()

    @model_validator(mode="after")
    def measurement_matches_status(self):
        if self.status is FindingStatus.PRESENT and self.value_mm is None:
            raise ValueError("A PRESENT measurement requires a numeric value")
        if self.status is FindingStatus.ABSENT and self.value_mm is not None:
            raise ValueError("An ABSENT measurement cannot include a numeric value")
        if self.value_mm is not None and self.status is FindingStatus.UNKNOWN:
            object.__setattr__(self, "status", FindingStatus.PRESENT)
        return self


class CytologyStatus(str, Enum):
    NOT_PERFORMED = "NOT_PERFORMED"
    NEGATIVE = "NEGATIVE"
    SUSPICIOUS = "SUSPICIOUS"
    POSITIVE = "POSITIVE"
    UNKNOWN = "UNKNOWN"


class CytologyAssessment(StrictSchema):
    status: CytologyStatus = CytologyStatus.UNKNOWN
    evidence: tuple[EvidenceSource, ...] = ()


class CA19Status(str, Enum):
    INCREASED = "INCREASED"
    NORMAL = "NORMAL"
    UNKNOWN = "UNKNOWN"


class CA19Assessment(StrictSchema):
    status: CA19Status = CA19Status.UNKNOWN
    value: float | None = Field(default=None, allow_inf_nan=False)
    unit: str | None = Field(default=None, max_length=64)
    reference_range: str | None = Field(default=None, max_length=256)
    reference_upper_limit: float | None = Field(default=None, allow_inf_nan=False)
    measured_at: datetime | None = None
    evidence: tuple[EvidenceSource, ...] = ()


class TimedDiabetesEvent(StrictSchema):
    status: FindingStatus = FindingStatus.UNKNOWN
    occurred_at: date | None = None
    evidence: tuple[EvidenceSource, ...] = ()


class MeasurementComparability(str, Enum):
    COMPARABLE = "COMPARABLE"
    INCOMPARABLE = "INCOMPARABLE"
    UNKNOWN = "UNKNOWN"


class LongitudinalMeasurements(StrictSchema):
    previous: Measurement | None = None
    current: Measurement | None = None
    comparability: MeasurementComparability = MeasurementComparability.UNKNOWN


class ClinicalContext(StrictSchema):
    """Structured facts only; omitted findings default to UNKNOWN, never ABSENT."""

    evaluated_at: datetime
    assessment_date: date | None = None
    lesion_location: CodedFact[LesionLocation] = Field(default_factory=CodedFact)
    obstructive_jaundice: Fact = Field(default_factory=Fact)
    mural_nodule_presence: Fact = Field(default_factory=Fact)
    mural_nodule_enhancing: Fact = Field(default_factory=Fact)
    mural_nodule_size: Measurement = Field(default_factory=Measurement)
    solid_component: Fact = Field(default_factory=Fact)
    mpd_diameter: Measurement = Field(default_factory=Measurement)
    cytology: CytologyAssessment = Field(default_factory=CytologyAssessment)
    acute_pancreatitis: Fact = Field(default_factory=Fact)
    serum_ca19_9: CA19Assessment = Field(default_factory=CA19Assessment)
    diabetes_status: Fact = Field(default_factory=Fact)
    new_onset_diabetes: TimedDiabetesEvent = Field(default_factory=TimedDiabetesEvent)
    acute_diabetes_exacerbation: TimedDiabetesEvent = Field(default_factory=TimedDiabetesEvent)
    cyst_maximum_diameter: Measurement = Field(default_factory=Measurement)
    cyst_wall_thickened: Fact = Field(default_factory=Fact)
    cyst_wall_enhancing: Fact = Field(default_factory=Fact)
    abrupt_duct_caliber_change: Fact = Field(default_factory=Fact)
    distal_pancreatic_atrophy: Fact = Field(default_factory=Fact)
    lymphadenopathy: Fact = Field(default_factory=Fact)
    longitudinal_measurements: LongitudinalMeasurements = Field(default_factory=LongitudinalMeasurements)

    @field_validator("evaluated_at")
    @classmethod
    def evaluation_time_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must include a timezone")
        return value


class RuleCategory(str, Enum):
    HIGH_RISK_STIGMATA = "HIGH_RISK_STIGMATA"
    WORRISOME_FEATURE = "WORRISOME_FEATURE"


class RuleStatus(str, Enum):
    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class AssessmentStatus(str, Enum):
    EVALUATED = "EVALUATED"
    PARTIALLY_EVALUATED = "PARTIALLY_EVALUATED"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RuleEvaluation(StrictSchema):
    rule_code: str
    category: RuleCategory
    status: RuleStatus
    criterion: str
    observed_values: dict[str, object] = Field(default_factory=dict)
    threshold: dict[str, object] = Field(default_factory=dict)
    trigger_reasons: tuple[str, ...] = ()
    evidence: tuple[EvidenceSource, ...] = ()
    missing_data: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class GuidelineVersion(StrictSchema):
    id: str = "KYOTO"
    version: str = "2024"


class EngineVersion(StrictSchema):
    name: str = "CystGuard Kyoto Rule Engine"
    version: str = "1.0.0"


class ClinicalDecisionBoundary(StrictSchema):
    doctor_decision_required: bool = True


class KyotoAssessment(StrictSchema):
    guideline: GuidelineVersion
    engine: EngineVersion
    assessment_status: AssessmentStatus
    evaluated_at: datetime
    assessment_date: date | None
    high_risk_stigmata: tuple[RuleEvaluation, ...]
    worrisome_features: tuple[RuleEvaluation, ...]
    rule_evaluations: tuple[RuleEvaluation, ...]
    not_evaluable_rules: tuple[RuleEvaluation, ...]
    missing_data: tuple[str, ...]
    evidence: tuple[EvidenceSource, ...]
    clinical_decision: ClinicalDecisionBoundary = Field(default_factory=ClinicalDecisionBoundary)
    not_applicable: bool = False
