from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import CA19Assessment, CA19Status, Fact, FindingStatus, Measurement, TimedDiabetesEvent


def rules(result): return {r.rule_code: r for r in result.rule_evaluations}


def fact(status): return Fact(status=FindingStatus(status))


def test_wf01_02_09_statuses(context):
    engine = KyotoEngine()
    for code, field in (("WF-01", "acute_pancreatitis"), ("WF-09", "lymphadenopathy")):
        for state, expected in (("PRESENT", "TRIGGERED"), ("ABSENT", "NOT_TRIGGERED"), ("UNKNOWN", "NOT_EVALUABLE")):
            assert rules(engine.evaluate(context.model_copy(update={field: fact(state)})))[code].status.value == expected
    for state, expected in ((CA19Status.NORMAL, "NOT_TRIGGERED"), (CA19Status.INCREASED, "TRIGGERED"), (CA19Status.UNKNOWN, "NOT_EVALUABLE")):
        assert rules(engine.evaluate(context.model_copy(update={"serum_ca19_9": CA19Assessment(status=state, value=999)})))["WF-02"].status.value == expected


def test_wf03_within_outside_and_unknown(context):
    engine = KyotoEngine()
    event = lambda d: TimedDiabetesEvent(status=FindingStatus.PRESENT, occurred_at=d)
    assert rules(engine.evaluate(context.model_copy(update={"new_onset_diabetes": event(context.assessment_date)})))["WF-03"].status.value == "TRIGGERED"
    old = context.model_copy(update={"new_onset_diabetes": event(context.assessment_date.replace(year=2024)), "acute_diabetes_exacerbation": TimedDiabetesEvent(status=FindingStatus.ABSENT)})
    assert rules(engine.evaluate(old))["WF-03"].status.value == "NOT_TRIGGERED"
    assert rules(engine.evaluate(context))["WF-03"].status.value == "NOT_EVALUABLE"


def test_wf04_and_wf07_boundaries(context):
    engine = KyotoEngine()
    for value, expected in ((29.9, "NOT_TRIGGERED"), (30, "TRIGGERED"), (30.1, "TRIGGERED")):
        assert rules(engine.evaluate(context.model_copy(update={"cyst_maximum_diameter": Measurement(value_mm=value)})))["WF-04"].status.value == expected
    for value, hrs, wf in ((4.9, "NOT_TRIGGERED", "NOT_TRIGGERED"), (5, "NOT_TRIGGERED", "TRIGGERED"), (9.9, "NOT_TRIGGERED", "TRIGGERED"), (10, "TRIGGERED", "NOT_TRIGGERED")):
        r = rules(engine.evaluate(context.model_copy(update={"mpd_diameter": Measurement(value_mm=value)})))
        assert (r["HRS-03"].status.value, r["WF-07"].status.value) == (hrs, wf)


def test_wf05_boundary_and_wf06_wall(context):
    engine = KyotoEngine()
    for value, expected in ((4.9, "TRIGGERED"), (5.0, "NOT_TRIGGERED")):
        c = context.model_copy(update={"mural_nodule_enhancing": fact("PRESENT"), "mural_nodule_size": Measurement(value_mm=value)})
        assert rules(engine.evaluate(c))["WF-05"].status.value == expected
    for t, e, reason in (("PRESENT", "ABSENT", "THICKENED_WALL"), ("ABSENT", "PRESENT", "ENHANCING_WALL"), ("PRESENT", "PRESENT", "BOTH")):
        c = context.model_copy(update={"cyst_wall_thickened": fact(t), "cyst_wall_enhancing": fact(e)})
        assert reason in rules(engine.evaluate(c))["WF-06"].trigger_reasons
