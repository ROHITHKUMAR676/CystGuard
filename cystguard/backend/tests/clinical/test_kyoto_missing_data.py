from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import Measurement


def test_unknown_stays_not_evaluable_and_missing_is_specific(context):
    result = KyotoEngine().evaluate(context)
    rules = {r.rule_code: r for r in result.rule_evaluations}
    assert rules["HRS-03"].status.value == "NOT_EVALUABLE"
    assert "mpd_diameter_mm" in rules["HRS-03"].missing_data
    assert rules["HRS-03"].status.value != "NOT_TRIGGERED"


def test_missing_one_field_does_not_hide_independent_trigger(context):
    result = KyotoEngine().evaluate(context.model_copy(update={"acute_pancreatitis": __import__("app.clinical.kyoto.schemas", fromlist=["Fact"]).Fact(status="PRESENT")}))
    rules = {r.rule_code: r for r in result.rule_evaluations}
    assert rules["WF-01"].status.value == "TRIGGERED"
    assert rules["HRS-03"].status.value == "NOT_EVALUABLE"
