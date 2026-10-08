from datetime import date
from math import isfinite

from app.mri.models import MRIStudy, StudyMeasurement


def normalize_mm(value: float, unit: str) -> float | None:
    unit = unit.strip().lower()
    if unit == "mm":
        return value
    if unit == "cm":
        return value * 10
    return None


def compare_measurements(previous: StudyMeasurement | None, current: StudyMeasurement | None,
                         previous_date: date | None, current_date: date | None) -> dict:
    if previous is None or current is None:
        return {"status": "INSUFFICIENT_DATA", "direction": "UNKNOWN", "change": None, "growth_rate_mm_per_year": None}
    if previous.finding_status or current.finding_status:
        a, b = previous.finding_status, current.finding_status
        if "UNKNOWN" in (a, b):
            direction = "UNKNOWN"
        elif a == "ABSENT" and b == "PRESENT":
            direction = "NEW"
        elif a == "PRESENT" and b == "ABSENT":
            direction = "RESOLVED"
        else:
            direction = "UNCHANGED"
        return {"status": "CALCULATED" if direction != "UNKNOWN" else "INSUFFICIENT_DATA", "direction": direction, "change": None, "growth_rate_mm_per_year": None}
    if previous.verification_status != "VERIFIED" or current.verification_status != "VERIFIED":
        return {"status": "INSUFFICIENT_DATA", "direction": "UNKNOWN", "change": None, "growth_rate_mm_per_year": None}
    if previous.comparability != "COMPARABLE" or current.comparability != "COMPARABLE":
        return {"status": "INCOMPARABLE", "direction": "NOT_COMPARABLE", "change": None, "growth_rate_mm_per_year": None}
    if previous_date is None or current_date is None or current_date <= previous_date:
        return {"status": "NOT_CALCULABLE", "direction": "UNKNOWN", "change": None, "growth_rate_mm_per_year": None}
    a, b = normalize_mm(previous.value, previous.unit or ""), normalize_mm(current.value, current.unit or "")
    if a is None or b is None or not isfinite(a) or not isfinite(b):
        return {"status": "INCOMPARABLE", "direction": "NOT_COMPARABLE", "change": None, "growth_rate_mm_per_year": None}
    delta = b - a
    direction = "INCREASED" if delta > 0 else "DECREASED" if delta < 0 else "UNCHANGED"
    elapsed_years = (current_date - previous_date).days / 365.2425
    growth_rate = delta / elapsed_years if current.feature in {"cyst_size", "cyst_maximum_diameter"} else None
    return {"status": "CALCULATED", "direction": direction, "change": delta, "growth_rate_mm_per_year": growth_rate}


def what_changed(previous: MRIStudy, current: MRIStudy) -> dict:
    by_feature = {m.feature: m for m in previous.measurements}
    results = []
    for measurement in current.measurements:
        old = by_feature.get(measurement.feature)
        result = compare_measurements(old, measurement, (old.measured_at or previous.study_date) if old else previous.study_date,
                                     measurement.measured_at or current.study_date)
        results.append({"feature": measurement.feature, "previous_value": old.value if old else old.finding_status if old else None,
                        "current_value": measurement.value if measurement.value is not None else measurement.finding_status,
                        "unit": measurement.unit, **result})
    previous_assessments = getattr(previous, "assessments", [])
    current_assessments = getattr(current, "assessments", [])
    old_assessment = previous_assessments[-1] if previous_assessments else None
    new_assessment = current_assessments[-1] if current_assessments else None
    comparable_scores = bool(old_assessment and new_assessment and old_assessment.model_id == new_assessment.model_id
                             and old_assessment.model_version == new_assessment.model_version
                             and old_assessment.threshold == new_assessment.threshold
                             and old_assessment.raw_score is not None and new_assessment.raw_score is not None)
    profile_changed = bool(old_assessment and new_assessment and old_assessment.risk_class != new_assessment.risk_class)
    changed = any(item["direction"] not in {"UNCHANGED", "UNKNOWN"} for item in results) or profile_changed
    return {"comparison_status": "CHANGES_DETECTED" if changed else "NO_VERIFIED_CHANGE" if results else "INSUFFICIENT_DATA",
            "previous_study_id": previous.id, "current_study_id": current.id, "changes": results,
            "risk_profile": {"previous_class": old_assessment.risk_class if old_assessment else None,
                             "current_class": new_assessment.risk_class if new_assessment else None,
                             "class_changed": profile_changed,
                             "raw_score_delta": new_assessment.raw_score - old_assessment.raw_score if comparable_scores else None,
                             "raw_score_semantics": "not a probability"},
            "doctor_review_required": bool(results) or profile_changed, "diagnosis": None}
