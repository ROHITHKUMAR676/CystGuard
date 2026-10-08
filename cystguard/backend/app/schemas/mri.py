from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.mri.models import InputQualityStatus, MRIFileFormat, MRIStudyStatus, PredictionStatus
from app.clinical.kyoto.schemas import KyotoAssessment
from app.clinical.trust.schemas import TrustResult
from app.explanation.schemas import ExplanationRead


class MRIStudyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    modality: str
    file_format: MRIFileFormat
    uploaded_at: datetime
    study_date: date | None = None
    status: MRIStudyStatus
    error_message: str | None


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mri_study_id: str
    model_id: str
    model_version: str
    architecture: str | None = None
    risk_class: str | None
    raw_score: float | None
    threshold: float | None
    prediction_status: PredictionStatus
    input_quality_status: InputQualityStatus
    fallback_used: bool
    error_message: str | None
    created_at: datetime
    clinical_context: dict | None = None
    guideline: KyotoAssessment | None = Field(default=None, validation_alias="guideline_result")
    trust: TrustResult | None = Field(default=None, validation_alias="trust_result")
    explanation: ExplanationRead | None = Field(default=None, validation_alias="explanation_result")


class MRIAnalysisResponse(BaseModel):
    mri_study: MRIStudyRead
    assessment: AssessmentRead
