import httpx
from httpx import Request

from app.config import Settings
from app.explanation.explanation_service import build_explanation
from app.explanation.sarvam_service import explain_with_sarvam


def _settings(key="test-key"):
    return Settings(database_url="sqlite://", sarvam_api_key=key, secret_key="test", sarvam_timeout_seconds=0.01)


def _response(content):
    return httpx.Response(200, request=Request("POST", "https://sarvam.test"), json={"model": "sarvam-105b", "choices": [{"message": {"content": content}}]})


def test_missing_sarvam_key_uses_no_external_call(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not call")))
    assert explain_with_sarvam({}, _settings(key="")) is None


def test_sarvam_structured_success(monkeypatch):
    data = {"summary": "Stored facts only", "ai_explanation": "AI result", "clinical_explanation": "Kyoto", "trust_explanation": "Not calibrated", "concordance_explanation": "Review", "longitudinal_explanation": "Unavailable", "missing_information": [], "review_reasons": []}
    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: _response(__import__("json").dumps(data)))
    result = explain_with_sarvam({"ai": {"risk_class": "HIGH_RISK"}}, _settings())
    assert result[0].summary == "Stored facts only"
    assert result[1] == "sarvam-105b"


def test_sarvam_malformed_response_falls_back(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: _response('{"summary": "missing required fields"}'))
    assert explain_with_sarvam({}, _settings()) is None


def test_sarvam_unavailable_and_timeout_fall_back(monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr("httpx.post", unavailable)
    assert explain_with_sarvam({}, _settings()) is None
    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")
    monkeypatch.setattr("httpx.post", timeout)
    assert explain_with_sarvam({}, _settings()) is None


def test_service_failure_keeps_structured_fallback_available(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("unavailable")))
    result = build_explanation({"ai": {"prediction_status": "FAILED"}}, _settings())
    assert result["provider"] == "DETERMINISTIC"
    assert result["service_message"] == "Explanation service unavailable. Structured assessment remains available."
