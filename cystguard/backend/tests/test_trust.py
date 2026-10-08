from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import (
    CA19Assessment, CA19Status, CodedFact, ClinicalContext, CytologyAssessment,
    CytologyStatus, Fact, FindingStatus, LesionLocation, LongitudinalMeasurements,
    Measurement, MeasurementComparability, TimedDiabetesEvent,
)
from app.clinical.trust import AIOutput, CalibrationResult, TrustService
from app.clinical.trust.schemas import AIRiskClass, CalibrationStatus, TrustStatus


def no_feature_context():
    return KyotoEngine().evaluate(ClinicalContext(
        evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc), assessment_date=date(2026, 1, 1),
        lesion_location=CodedFact(status=FindingStatus.PRESENT, value=LesionLocation.BODY),
        obstructive_jaundice=Fact(status=FindingStatus.ABSENT),
        mural_nodule_enhancing=Fact(status=FindingStatus.ABSENT), solid_component=Fact(status=FindingStatus.ABSENT),
        mpd_diameter=Measurement(value_mm=4.0), cytology=CytologyAssessment(status=CytologyStatus.NEGATIVE),
        acute_pancreatitis=Fact(status=FindingStatus.ABSENT), serum_ca19_9=CA19Assessment(status=CA19Status.NORMAL),
        new_onset_diabetes=TimedDiabetesEvent(status=FindingStatus.ABSENT),
        acute_diabetes_exacerbation=TimedDiabetesEvent(status=FindingStatus.ABSENT),
        cyst_maximum_diameter=Measurement(value_mm=10.0),
        cyst_wall_thickened=Fact(status=FindingStatus.ABSENT), cyst_wall_enhancing=Fact(status=FindingStatus.ABSENT),
        abrupt_duct_caliber_change=Fact(status=FindingStatus.ABSENT),
        distal_pancreatic_atrophy=Fact(status=FindingStatus.ABSENT), lymphadenopathy=Fact(status=FindingStatus.ABSENT),
        longitudinal_measurements=LongitudinalMeasurements(
            previous=Measurement(value_mm=10, measured_at=date(2024, 1, 1)),
            current=Measurement(value_mm=11, measured_at=date(2025, 1, 1)),
            comparability=MeasurementComparability.COMPARABLE,
        ),
    ))


def high_hrs_context():
    return KyotoEngine().evaluate(ClinicalContext(
        evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc), mpd_diameter=Measurement(value_mm=10.0),
    ))


def wf_only_context():
    return KyotoEngine().evaluate(ClinicalContext(
        evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        acute_pancreatitis=Fact(status=FindingStatus.PRESENT),
    ))


def ai(risk, score=0.61, threshold=0.5, version="cystx-baseline-v1"):
    return AIOutput(model_id="cystx", model_version=version, risk_class=risk, raw_score=score, threshold=threshold)


@pytest.mark.parametrize(("risk", "kyoto", "expected"), [
    (AIRiskClass.HIGH_RISK, high_hrs_context, TrustStatus.CONCORDANT_HIGH),
    (AIRiskClass.NO_LOW_RISK, no_feature_context, TrustStatus.CONCORDANT_LOWER),
    (AIRiskClass.HIGH_RISK, no_feature_context, TrustStatus.DISCORDANT),
    (AIRiskClass.NO_LOW_RISK, high_hrs_context, TrustStatus.DISCORDANT),
    (AIRiskClass.HIGH_RISK, wf_only_context, TrustStatus.REVIEW),
    (AIRiskClass.NO_LOW_RISK, wf_only_context, TrustStatus.REVIEW),
])
def test_concordance_matrix(risk, kyoto, expected):
    result = TrustService().evaluate(ai(risk), kyoto(), evaluated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert result.trust_status is expected
    assert result.doctor_review_required is (expected is not TrustStatus.CONCORDANT_LOWER)


def test_missing_kyoto_data_is_indeterminate_not_lower():
    result = TrustService().evaluate(ai(AIRiskClass.NO_LOW_RISK), KyotoEngine().evaluate(
        ClinicalContext(evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    ))
    assert result.trust_status is TrustStatus.INDETERMINATE
    assert "mpd_diameter_mm" in result.kyoto.missing_data
    assert result.kyoto.status.value == "INDETERMINATE"
    assert "KYOTO_MISSING_REQUIRED_DATA" in result.concordance.reason_codes


def test_complete_no_feature_evidence_can_concord_lower():
    result = TrustService().evaluate(ai(AIRiskClass.NO_LOW_RISK), no_feature_context())
    assert result.trust_status is TrustStatus.CONCORDANT_LOWER
    assert result.kyoto.status.value == "LOWER_RISK_EVIDENCE"
    assert not result.kyoto.not_evaluable_rules


@pytest.mark.parametrize(("field", "value"), [("raw_score", -0.01), ("raw_score", 1.01), ("threshold", -0.01), ("threshold", 1.01)])
def test_invalid_score_or_threshold_rejected(field, value):
    kwargs = dict(model_id="cystx", model_version="v1", risk_class=AIRiskClass.HIGH_RISK, raw_score=0.5, threshold=0.5)
    kwargs[field] = value
    with pytest.raises(ValidationError):
        AIOutput(**kwargs)


def test_decision_margin_and_equal_threshold():
    result = TrustService().evaluate(ai(AIRiskClass.HIGH_RISK, score=0.5, threshold=0.5), high_hrs_context())
    assert result.ai.decision_margin == 0
    assert result.ai.decision_margin_label == "DECISION_MARGIN"
    assert result.ai.risk_class is AIRiskClass.HIGH_RISK


def test_calibration_and_uncertainty_unavailable_by_default():
    result = TrustService().evaluate(ai(AIRiskClass.HIGH_RISK), high_hrs_context())
    assert result.calibration.available is False
    assert result.calibration.status is CalibrationStatus.NOT_CALIBRATED
    assert result.calibration.calibrated_score is None
    assert result.uncertainty.status.value == "NOT_CALIBRATED"
    assert result.ai.raw_score == 0.61


def test_supplied_calibration_metadata_and_versions_are_preserved():
    calibration = CalibrationResult(
        available=True, method="isotonic", model_version="cystx-baseline-v1",
        calibration_dataset="validated-cohort-v1", calibrated_score=0.42,
        status=CalibrationStatus.CALIBRATED,
    )
    result = TrustService().evaluate(ai(AIRiskClass.HIGH_RISK), high_hrs_context(), calibration=calibration,
                                     evaluated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert result.ai.model_version == "cystx-baseline-v1"
    assert result.kyoto.guideline_version == "2024"
    assert result.trust_engine.version == "1.0.0"
    assert result.evaluated_at == datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert result.calibration == calibration


def test_calibration_version_mismatch_rejected():
    calibration = CalibrationResult(available=False, model_version="other-version")
    with pytest.raises(ValueError, match="model_version"):
        TrustService().evaluate(ai(AIRiskClass.HIGH_RISK), high_hrs_context(), calibration=calibration)


def test_safety_fields_and_ai_unavailable():
    result = TrustService().evaluate(AIOutput(model_id="cystx", model_version="v1", risk_class=None), no_feature_context())
    assert result.trust_status is TrustStatus.INDETERMINATE
    assert result.doctor_review_required
    payload = result.model_dump_json().lower()
    for forbidden in ("cancer_probability", "diagnosis", "surgery_recommended", "treatment_recommended", "confidence"):
        assert forbidden not in payload


def test_calibration_rejects_fabricated_or_incomplete_score():
    with pytest.raises(ValidationError):
        CalibrationResult(available=True, model_version="v1", calibrated_score=0.5)
    with pytest.raises(ValidationError):
        CalibrationResult(available=False, model_version="v1", calibrated_score=0.5)
