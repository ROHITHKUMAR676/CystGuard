from datetime import date
from types import SimpleNamespace

from app.services.longitudinal_service import compare_measurements, normalize_mm, what_changed
from app.services.surveillance_service import calculate_plan_status


def measure(value, unit="mm", verified="VERIFIED", comparable="COMPARABLE", finding=None, feature="cyst_size"):
    return SimpleNamespace(value=value, unit=unit, verification_status=verified,
                           comparability=comparable, finding_status=finding, feature=feature, measured_at=None)


def test_growth_and_safe_unit_normalization():
    result = compare_measurements(measure(22), measure(2.7, "cm"), date(2024, 1, 1), date(2025, 1, 1))
    assert result["status"] == "CALCULATED"
    assert round(result["change"], 2) == 5
    assert round(result["growth_rate_mm_per_year"], 1) == 5
    assert normalize_mm(4, "inch") is None


def test_missing_unverified_and_incomparable_are_not_calculated():
    assert compare_measurements(None, measure(2), date(2023, 1, 1), date(2024, 1, 1))["status"] == "INSUFFICIENT_DATA"
    assert compare_measurements(measure(2), measure(3, verified="UNVERIFIED"), date(2023, 1, 1), date(2024, 1, 1))["status"] == "INSUFFICIENT_DATA"
    assert compare_measurements(measure(2), measure(3, comparable="INCOMPARABLE"), date(2023, 1, 1), date(2024, 1, 1))["status"] == "INCOMPARABLE"
    assert compare_measurements(measure(2), measure(3), None, date(2024, 1, 1))["status"] == "NOT_CALCULABLE"


def test_explicit_finding_transitions_and_unknown():
    assert compare_measurements(measure(None, finding="ABSENT"), measure(None, finding="PRESENT"), None, None)["direction"] == "NEW"
    assert compare_measurements(measure(None, finding="PRESENT"), measure(None, finding="ABSENT"), None, None)["direction"] == "RESOLVED"
    assert compare_measurements(measure(None, finding="UNKNOWN"), measure(None, finding="PRESENT"), None, None)["direction"] == "UNKNOWN"


def test_what_changed_is_factual_and_does_not_interpret_scores():
    old = SimpleNamespace(id="old", study_date=date(2024, 1, 1), measurements=[measure(20)], assessments=[])
    new = SimpleNamespace(id="new", study_date=date(2025, 1, 1), measurements=[measure(25)], assessments=[])
    summary = what_changed(old, new)
    assert summary["comparison_status"] == "CHANGES_DETECTED"
    assert summary["doctor_review_required"] is True
    assert summary["diagnosis"] is None
    assert summary["risk_profile"]["raw_score_semantics"] == "not a probability"


def test_surveillance_due_status_boundaries():
    target = date(2025, 1, 10)
    assert calculate_plan_status(target, date(2025, 1, 9)) == "PLANNED"
    assert calculate_plan_status(target, target) == "DUE"
    assert calculate_plan_status(target, date(2025, 1, 11)) == "OVERDUE"
    assert calculate_plan_status(target, date(2026, 1, 1), "COMPLETED") == "COMPLETED"
