from app.clinical.kyoto.engine import KyotoEngine
from app.clinical.kyoto.schemas import AssessmentStatus, Fact, FindingStatus, Measurement


def test_engine_is_deterministic_and_bounded(context, evidence):
    c = context.model_copy(update={"acute_pancreatitis": Fact(status=FindingStatus.PRESENT, evidence=(evidence,)), "mpd_diameter": Measurement(value_mm=10, evidence=(evidence,))})
    engine = KyotoEngine()
    first, second = engine.evaluate(c), engine.evaluate(c)
    assert first == second
    assert first.engine.version == "1.0.0" and first.guideline.version == "2024"
    assert first.high_risk_stigmata and first.worrisome_features
    serialized = first.model_dump_json().lower()
    for prohibited in ("cancer_probability", "surgery_recommended", "diagnosis"):
        assert prohibited not in serialized
    assert first.clinical_decision.doctor_decision_required
    assert all(x.evidence for x in (*first.high_risk_stigmata, *first.worrisome_features))


def test_engine_has_no_db_or_model_imports():
    import pathlib
    root = pathlib.Path(__file__).parents[2] / "app" / "clinical" / "kyoto"
    source = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
    for forbidden in ("sqlalchemy", "torch", "cystx_inference", "external_llm"):
        assert forbidden not in source.lower()
