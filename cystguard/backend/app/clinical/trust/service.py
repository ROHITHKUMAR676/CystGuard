from datetime import datetime, timezone

from app.clinical.kyoto.schemas import KyotoAssessment
from app.clinical.trust.calibration import calibration_unavailable
from app.clinical.trust.concordance import compare, interpret_kyoto
from app.clinical.trust.schemas import AIOutput, AITrustView, CalibrationResult, TrustEngineVersion, TrustResult, TrustStatus
from app.clinical.trust.uncertainty import unavailable_uncertainty
from app.clinical.trust.version import TRUST_ENGINE_NAME, TRUST_ENGINE_VERSION


class TrustService:
    """Compare independent AI and Kyoto outputs; this service does not run either."""

    def evaluate(self, ai: AIOutput, kyoto_assessment: KyotoAssessment, *, calibration: CalibrationResult | None = None, evaluated_at: datetime | None = None) -> TrustResult:
        kyoto = interpret_kyoto(kyoto_assessment)
        concordance = compare(ai, kyoto)
        margin = abs(ai.raw_score - ai.threshold) if ai.raw_score is not None and ai.threshold is not None else None
        calibration_result = calibration or calibration_unavailable(ai.model_version)
        if calibration_result.model_version != ai.model_version:
            raise ValueError("Calibration model_version must match AI model_version")
        review_required = (
            concordance.status in {TrustStatus.DISCORDANT, TrustStatus.REVIEW, TrustStatus.INDETERMINATE}
            or bool(kyoto.hrs_present) or bool(kyoto.missing_data) or ai.risk_class is None
        )
        return TrustResult(
            trust_status=concordance.status,
            ai=AITrustView(model_id=ai.model_id, model_version=ai.model_version, risk_class=ai.risk_class,
                           raw_score=ai.raw_score, threshold=ai.threshold, decision_margin=margin),
            kyoto=kyoto, concordance=concordance, uncertainty=unavailable_uncertainty(),
            calibration=calibration_result,
            trust_engine=TrustEngineVersion(name=TRUST_ENGINE_NAME, version=TRUST_ENGINE_VERSION),
            evaluated_at=evaluated_at or datetime.now(timezone.utc),
            doctor_review_required=review_required,
        )
