from collections.abc import Iterable

from app.clinical.kyoto.schemas import (
    EvidenceSource,
    RuleCategory,
    RuleEvaluation,
    RuleStatus,
)
from app.clinical.kyoto.evaluation.evidence import unique_evidence


def rule_result(
    *,
    code: str,
    category: RuleCategory,
    status: RuleStatus,
    criterion: str,
    observed: dict[str, object] | None = None,
    threshold: dict[str, object] | None = None,
    reasons: Iterable[str] = (),
    evidence: Iterable[EvidenceSource] = (),
    missing: Iterable[str] = (),
    notes: Iterable[str] = (),
) -> RuleEvaluation:
    return RuleEvaluation(
        rule_code=code,
        category=category,
        status=status,
        criterion=criterion,
        observed_values=observed or {},
        threshold=threshold or {},
        trigger_reasons=tuple(reasons),
        evidence=unique_evidence(evidence),
        missing_data=tuple(dict.fromkeys(missing)),
        notes=tuple(notes),
    )
