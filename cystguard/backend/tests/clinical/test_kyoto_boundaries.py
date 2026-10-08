from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import Fact, FindingStatus


def test_wf08_requires_both_and_preserves_evidence(context, evidence):
    engine = KyotoEngine()
    for a, b, expected in (("PRESENT", "ABSENT", "NOT_TRIGGERED"), ("ABSENT", "PRESENT", "NOT_TRIGGERED"), ("PRESENT", "PRESENT", "TRIGGERED")):
        c = context.model_copy(update={"abrupt_duct_caliber_change": Fact(status=FindingStatus(a), evidence=(evidence,)), "distal_pancreatic_atrophy": Fact(status=FindingStatus(b), evidence=(evidence,))})
        rule = next(x for x in engine.evaluate(c).rule_evaluations if x.rule_code == "WF-08")
        assert rule.status.value == expected
        if expected == "TRIGGERED": assert rule.evidence == (evidence,)
