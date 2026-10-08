from datetime import datetime, timezone

from app.config import Settings, get_settings
from app.explanation.sarvam_service import explain_with_sarvam
from app.explanation.schemas import ExplanationContent


EXPLANATION_VERSION = "1.0.0"


def _fallback(facts: dict) -> ExplanationContent:
    ai = facts.get("ai") or {}
    guideline = facts.get("guideline") or {}
    trust = facts.get("trust") or {}
    concordance = (trust.get("concordance") or {})
    longitudinal = facts.get("longitudinal") or {}
    missing = list(guideline.get("missing_data") or [])
    review = []
    if trust.get("doctor_review_required"):
        review.append("The structured trust service requires clinician review.")
    if concordance.get("status") in {"DISCORDANT", "REVIEW", "INDETERMINATE"}:
        review.append("AI and guideline evidence require clinician review.")
    if missing:
        review.append("Clinical information is incomplete.")
    if ai.get("input_quality_status") != "ACCEPTABLE":
        review.append("MRI input quality was not evaluated as acceptable.")
    if not review:
        review.append("Clinician review remains required for this decision-support assessment.")
    if guideline.get("not_applicable"):
        clinical = "Kyoto 2024 was marked not applicable for the recorded non-IPMN cyst type."
    elif guideline:
        clinical = f"Kyoto 2024 evaluation status: {guideline.get('assessment_status', 'UNKNOWN')}. Findings and missing fields are listed in the structured assessment."
    else:
        clinical = "Guideline assessment is unavailable."
    score = ai.get("raw_score")
    ai_text = (f"{ai.get('model_id', 'Model')} {ai.get('model_version', '')} returned risk class {ai.get('risk_class', 'UNKNOWN')} and raw model score {score}. The score is not a calibrated probability." if score is not None else f"AI result is unavailable; status is {ai.get('prediction_status', 'UNKNOWN')}.")
    return ExplanationContent(
        summary="This explanation summarizes stored CystGuard outputs. It does not make a diagnosis or treatment recommendation.",
        ai_explanation=ai_text,
        clinical_explanation=clinical,
        trust_explanation=f"Trust status: {trust.get('trust_status', 'UNKNOWN')}. Uncertainty: {(trust.get('uncertainty') or {}).get('status', 'UNAVAILABLE')}. Calibration: {(trust.get('calibration') or {}).get('status', 'NOT_CALIBRATED')}.",
        concordance_explanation=f"AI and guideline comparison status: {concordance.get('status', 'UNKNOWN')}; reasons: {', '.join(concordance.get('reason_codes') or []) or 'not recorded'}.",
        longitudinal_explanation=(
            f"Recorded prior measurement: {longitudinal['previous'].get('value_mm')} mm on {longitudinal['previous'].get('measured_at')}; "
            f"recorded current measurement: {longitudinal['current'].get('value_mm')} mm on {longitudinal['current'].get('measured_at')}; "
            f"comparability: {longitudinal.get('comparability', 'UNKNOWN')}. Kyoto evaluates growth only when its requirements are met."
            if longitudinal.get("previous") and longitudinal.get("current")
            else f"Longitudinal data status: {longitudinal.get('status', 'UNAVAILABLE')}. No changes are inferred by this explanation."
        ),
        missing_information=missing,
        review_reasons=review,
    )


def build_explanation(facts: dict, settings: Settings | None = None, *, allow_sarvam: bool = True) -> dict:
    settings = settings or get_settings()
    generated = explain_with_sarvam(facts, settings) if allow_sarvam else None
    if generated is None:
        content, model, provider, status = _fallback(facts), None, "DETERMINISTIC", "FALLBACK"
        if allow_sarvam:
            content = content.model_copy(update={
                "summary": "Explanation service unavailable. Structured assessment remains available. " + content.summary
            })
    else:
        content, model = generated
        provider, status = "SARVAM", "GENERATED"
    return {
        **content.model_dump(mode="json"),
        "provider": provider,
        "model": model,
        "version": EXPLANATION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "service_message": "Explanation service unavailable. Structured assessment remains available." if allow_sarvam and generated is None else None,
    }
