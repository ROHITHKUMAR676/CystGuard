from app.clinical.kyoto.evaluation.evidence import unique_evidence
from app.clinical.kyoto.rules.hrs import HRS_EVALUATORS
from app.clinical.kyoto.rules.wf import WF_EVALUATORS
from app.clinical.kyoto.schemas import (
    AssessmentStatus, ClinicalContext, EngineVersion, GuidelineVersion,
    KyotoAssessment, RuleStatus,
)
from app.clinical.kyoto.version import RULE_ENGINE_NAME, RULE_ENGINE_VERSION


class KyotoEngine:
    """Pure deterministic evaluator over caller-supplied structured facts."""

    def evaluate(self, context: ClinicalContext) -> KyotoAssessment:
        evaluations = tuple(fn(context) for fn in (*HRS_EVALUATORS, *WF_EVALUATORS))
        unresolved = tuple(r for r in evaluations if r.status is RuleStatus.NOT_EVALUABLE)
        evaluated_count = len(evaluations) - len(unresolved)
        if not evaluated_count:
            status = AssessmentStatus.NOT_EVALUABLE
        elif unresolved:
            status = AssessmentStatus.PARTIALLY_EVALUATED
        else:
            status = AssessmentStatus.EVALUATED
        return KyotoAssessment(
            guideline=GuidelineVersion(),
            engine=EngineVersion(name=RULE_ENGINE_NAME, version=RULE_ENGINE_VERSION),
            assessment_status=status,
            evaluated_at=context.evaluated_at,
            assessment_date=context.assessment_date,
            high_risk_stigmata=tuple(r for r in evaluations if r.category.value == "HIGH_RISK_STIGMATA" and r.status is RuleStatus.TRIGGERED),
            worrisome_features=tuple(r for r in evaluations if r.category.value == "WORRISOME_FEATURE" and r.status is RuleStatus.TRIGGERED),
            rule_evaluations=evaluations,
            not_evaluable_rules=unresolved,
            missing_data=tuple(dict.fromkeys(item for rule in evaluations for item in rule.missing_data)),
            evidence=unique_evidence(e for rule in evaluations for e in rule.evidence),
        )
