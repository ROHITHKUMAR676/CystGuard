from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExplanationContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=2000)
    ai_explanation: str = Field(max_length=2000)
    clinical_explanation: str = Field(max_length=2000)
    trust_explanation: str = Field(max_length=2000)
    concordance_explanation: str = Field(max_length=2000)
    longitudinal_explanation: str = Field(max_length=2000)
    missing_information: list[str] = Field(max_length=100)
    review_reasons: list[str] = Field(max_length=100)


class ExplanationRead(ExplanationContent):
    provider: str
    model: str | None
    version: str
    generated_at: datetime
    status: str
    service_message: str | None = None
