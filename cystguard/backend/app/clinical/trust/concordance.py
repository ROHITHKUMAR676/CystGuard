from app.clinical.kyoto.schemas import KyotoAssessment, RuleStatus
from app.clinical.trust.schemas import AIOutput, AIRiskClass, ConcordanceView, KyotoEvidenceStatus, KyotoTrustView, TrustStatus


def interpret_kyoto(assessment: KyotoAssessment) -> KyotoTrustView:
    hrs = tuple(r.rule_code for r in assessment.high_risk_stigmata if r.status is RuleStatus.TRIGGERED)
    wf = tuple(r.rule_code for r in assessment.worrisome_features if r.status is RuleStatus.TRIGGERED)
    if assessment.not_applicable:
        status = KyotoEvidenceStatus.INDETERMINATE
    elif hrs:
        status = KyotoEvidenceStatus.HIGH_RISK_EVIDENCE
    elif wf:
        status = KyotoEvidenceStatus.WORRISOME_EVIDENCE
    elif assessment.not_evaluable_rules or assessment.missing_data:
        status = KyotoEvidenceStatus.INDETERMINATE
    else:
        status = KyotoEvidenceStatus.LOWER_RISK_EVIDENCE
    return KyotoTrustView(
        hrs_present=hrs, wf_present=wf, status=status,
        missing_data=assessment.missing_data,
        not_evaluable_rules=tuple(r.rule_code for r in assessment.not_evaluable_rules),
        guideline_id=assessment.guideline.id, guideline_version=assessment.guideline.version,
    )


def compare(ai: AIOutput, kyoto: KyotoTrustView) -> ConcordanceView:
    reasons = []
    if ai.risk_class is AIRiskClass.HIGH_RISK:
        reasons.append("AI_HIGH_RISK")
    elif ai.risk_class is AIRiskClass.NO_LOW_RISK:
        reasons.append("AI_NO_LOW_RISK")
    else:
        reasons.append("AI_OUTPUT_UNAVAILABLE")

    if kyoto.status is KyotoEvidenceStatus.HIGH_RISK_EVIDENCE:
        reasons.append("KYOTO_HRS_PRESENT")
    elif kyoto.status is KyotoEvidenceStatus.WORRISOME_EVIDENCE:
        reasons.append("KYOTO_WF_PRESENT")
    elif kyoto.status is KyotoEvidenceStatus.LOWER_RISK_EVIDENCE:
        reasons.append("KYOTO_NO_HRS_OR_WF")
    else:
        reasons.append("KYOTO_MISSING_REQUIRED_DATA")

    if ai.risk_class is None or kyoto.status is KyotoEvidenceStatus.INDETERMINATE:
        status = TrustStatus.INDETERMINATE
    elif kyoto.status is KyotoEvidenceStatus.WORRISOME_EVIDENCE:
        status = TrustStatus.REVIEW
    elif kyoto.status is KyotoEvidenceStatus.HIGH_RISK_EVIDENCE and ai.risk_class is AIRiskClass.HIGH_RISK:
        status = TrustStatus.CONCORDANT_HIGH
        reasons.append("AI_KYOTO_AGREE_HIGH")
    elif kyoto.status is KyotoEvidenceStatus.LOWER_RISK_EVIDENCE and ai.risk_class is AIRiskClass.NO_LOW_RISK:
        status = TrustStatus.CONCORDANT_LOWER
        reasons.append("AI_KYOTO_AGREE_LOWER")
    else:
        status = TrustStatus.DISCORDANT
        reasons.append("AI_KYOTO_DISCORDANT")
    return ConcordanceView(status=status, reason_codes=tuple(reasons))
