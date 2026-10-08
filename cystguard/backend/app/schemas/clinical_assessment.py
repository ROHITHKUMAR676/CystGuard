from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.clinical.kyoto.schemas import ClinicalContext


class CystType(str, Enum):
    IPMN = "IPMN"
    NON_IPMN = "NON_IPMN"
    UNKNOWN = "UNKNOWN"


class ClinicalAssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cyst_type: CystType = CystType.UNKNOWN
    clinical_context: ClinicalContext


class AssessmentPipelineRead(BaseModel):
    assessment_id: str
    clinical_context: dict
    guideline: dict
    trust: dict
    concordance: dict
    explanation: dict
    longitudinal: dict

