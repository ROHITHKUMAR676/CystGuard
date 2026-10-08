from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import (CodedFact, CytologyAssessment, CytologyStatus, FindingStatus, LesionLocation, Measurement)


def rules(result): return {r.rule_code: r for r in result.rule_evaluations}


def test_hrs01_head_jaundice(context, evidence):
    from tests.clinical.conftest import present
    c = context.model_copy(update={"lesion_location": CodedFact(status=FindingStatus.PRESENT, value=LesionLocation.HEAD, evidence=(evidence,)), "obstructive_jaundice": present((evidence,))})
    r = rules(KyotoEngine().evaluate(c))["HRS-01"]
    assert r.status.value == "TRIGGERED" and r.evidence == (evidence,)


def test_hrs01_unknown_location_and_nonhead_jaundice(context):
    from tests.clinical.conftest import present
    engine = KyotoEngine()
    assert rules(engine.evaluate(context.model_copy(update={"obstructive_jaundice": present()})))["HRS-01"].status.value == "NOT_EVALUABLE"
    nonhead = context.model_copy(update={"lesion_location": CodedFact(status=FindingStatus.PRESENT, value=LesionLocation.BODY), "obstructive_jaundice": present()})
    assert rules(engine.evaluate(nonhead))["HRS-01"].status.value == "NOT_TRIGGERED"


def test_hrs02_nodule_boundary_and_solid(context):
    from tests.clinical.conftest import absent, present
    engine = KyotoEngine()
    for value, expected in ((4.9, "NOT_TRIGGERED"), (5.0, "TRIGGERED")):
        c = context.model_copy(update={"mural_nodule_enhancing": present(), "mural_nodule_size": Measurement(value_mm=value), "solid_component": absent()})
        assert rules(engine.evaluate(c))["HRS-02"].status.value == expected
    c = context.model_copy(update={"solid_component": present()})
    assert "SOLID_COMPONENT" in rules(engine.evaluate(c))["HRS-02"].trigger_reasons


def test_hrs03_and_cytology(context):
    engine = KyotoEngine()
    for value, expected in ((9.9, "NOT_TRIGGERED"), (10.0, "TRIGGERED")):
        assert rules(engine.evaluate(context.model_copy(update={"mpd_diameter": Measurement(value_mm=value)})))["HRS-03"].status.value == expected
    for value, expected in ((CytologyStatus.NOT_PERFORMED, "NOT_EVALUABLE"), (CytologyStatus.NEGATIVE, "NOT_TRIGGERED"), (CytologyStatus.SUSPICIOUS, "TRIGGERED"), (CytologyStatus.POSITIVE, "TRIGGERED"), (CytologyStatus.UNKNOWN, "NOT_EVALUABLE")):
        assert rules(engine.evaluate(context.model_copy(update={"cytology": CytologyAssessment(status=value)})))["HRS-04"].status.value == expected
