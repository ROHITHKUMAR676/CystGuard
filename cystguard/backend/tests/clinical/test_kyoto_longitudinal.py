from datetime import date

from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import LongitudinalMeasurements, Measurement, MeasurementComparability


def wf10(context, previous, current, comparable=MeasurementComparability.COMPARABLE):
    pair = LongitudinalMeasurements(previous=previous, current=current, comparability=comparable)
    return next(x for x in KyotoEngine().evaluate(context.model_copy(update={"longitudinal_measurements": pair})).rule_evaluations if x.rule_code == "WF-10")


def test_growth_rate_threshold(context):
    start = date(2024, 1, 1)
    end = date(2025, 1, 1)
    for delta, expected in ((2.49, "NOT_TRIGGERED"), (2.5 * ((end-start).days / 365.2425), "TRIGGERED"), (2.51, "TRIGGERED")):
        r = wf10(context, Measurement(value_mm=10, measured_at=start), Measurement(value_mm=10+delta, measured_at=end))
        assert r.status.value == expected
        assert r.observed_values["previous_date"] == start.isoformat()
        assert r.observed_values["current_date"] == end.isoformat()


def test_growth_missing_invalid_and_incomparable(context):
    assert wf10(context, None, Measurement(value_mm=11, measured_at=date(2025,1,1))).status.value == "NOT_EVALUABLE"
    assert wf10(context, Measurement(value_mm=10, measured_at=date(2025,1,1)), Measurement(value_mm=11, measured_at=date(2024,1,1))).status.value == "NOT_EVALUABLE"
    assert wf10(context, Measurement(value_mm=10, measured_at=date(2024,1,1)), Measurement(value_mm=11, measured_at=date(2025,1,1)), MeasurementComparability.INCOMPARABLE).status.value == "NOT_EVALUABLE"
