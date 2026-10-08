from datetime import datetime, timezone

from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import (
    AssessmentStatus, ClinicalContext, ClinicalDecisionBoundary, EngineVersion,
    GuidelineVersion, KyotoAssessment,
)
from app.clinical.trust.schemas import AIOutput
from app.clinical.trust.service import TrustService
from app.explanation.explanation_service import build_explanation
from app.mri.models import Assessment, InputQualityStatus
from app.schemas.clinical_assessment import CystType


def evaluate_and_persist(assessment: Assessment, cyst_type: CystType, context: ClinicalContext) -> None:
    context_data = context.model_dump(mode="json")
    context_data["cyst_type"] = cyst_type.value
    assessment.clinical_context = context_data

    if cyst_type is CystType.NON_IPMN:
        guideline = KyotoAssessment(
            guideline=GuidelineVersion(), engine=EngineVersion(),
            assessment_status=AssessmentStatus.NOT_APPLICABLE,
            evaluated_at=context.evaluated_at, assessment_date=context.assessment_date,
            high_risk_stigmata=(), worrisome_features=(), rule_evaluations=(),
            not_evaluable_rules=(), missing_data=(), evidence=(),
            clinical_decision=ClinicalDecisionBoundary(), not_applicable=True,
        )
    else:
        guideline = KyotoEngine().evaluate(context)

    ai = AIOutput(
        model_id=assessment.model_id,
        model_version=assessment.model_version,
        risk_class=assessment.risk_class,
        raw_score=assessment.raw_score,
        threshold=assessment.threshold,
    )
    trust = TrustService().evaluate(ai, guideline)
    if assessment.input_quality_status is not InputQualityStatus.ACCEPTABLE:
        trust = trust.model_copy(update={"doctor_review_required": True})

    assessment.guideline_result = guideline.model_dump(mode="json")
    assessment.trust_result = trust.model_dump(mode="json")
    assessment.explanation_result = build_explanation({
        "ai": {"model_id": assessment.model_id, "model_version": assessment.model_version,
               "risk_class": assessment.risk_class, "raw_score": assessment.raw_score,
               "threshold": assessment.threshold, "prediction_status": assessment.prediction_status.value,
               "input_quality_status": assessment.input_quality_status.value},
        "clinical_context": context_data,
        "guideline": assessment.guideline_result,
        "trust": assessment.trust_result,
        "longitudinal": context_data.get("longitudinal_measurements") or {"status": "UNAVAILABLE"},
    }, allow_sarvam=False)


def empty_clinical_context() -> ClinicalContext:
    return ClinicalContext(evaluated_at=datetime.now(timezone.utc))
