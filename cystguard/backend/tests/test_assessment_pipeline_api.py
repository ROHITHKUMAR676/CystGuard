import gzip
from pathlib import Path

from app.ml.ml_service import MLPrediction, get_ml_service
from app.mri.models import Assessment


def _token(client):
    client.post("/api/v1/auth/register", json={
        "email": "assessment-doctor@example.test", "password": "strong-test-password", "role": "DOCTOR"
    })
    return client.post("/api/v1/auth/login", json={
        "email": "assessment-doctor@example.test", "password": "strong-test-password"
    }).json()["access_token"]


class KnownML:
    def analyze(self, path: Path):
        return MLPrediction("cystx", "baseline-test", "HIGH_RISK", 0.61, 0.5)


def _upload(client, token):
    header = bytearray(348)
    header[:4] = (348).to_bytes(4, "little")
    header[344:348] = b"n+1\x00"
    client.app.dependency_overrides[get_ml_service] = lambda: KnownML()
    response = client.post("/api/v1/mri/studies", headers={"Authorization": f"Bearer {token}"},
                           files={"upload": ("scan.nii.gz", gzip.compress(bytes(header) + b"\0" * 16))})
    client.app.dependency_overrides.pop(get_ml_service, None)
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_returns_unknown_kyoto_and_real_trust_state(client):
    token = _token(client)
    record = _upload(client, token)
    assessment = record["assessment"]
    assert assessment["guideline"]["guideline"]["id"] == "KYOTO"
    assert assessment["guideline"]["assessment_status"] == "NOT_EVALUABLE"
    assert assessment["guideline"]["missing_data"]
    assert assessment["trust"]["trust_status"] == "INDETERMINATE"
    assert assessment["trust"]["uncertainty"]["status"] == "NOT_CALIBRATED"
    assert assessment["trust"]["calibration"]["status"] == "NOT_CALIBRATED"
    assert assessment["explanation"]["provider"] == "DETERMINISTIC"


def test_saved_context_reaches_kyoto_trust_and_concordance(client):
    token = _token(client)
    assessment = _upload(client, token)["assessment"]
    response = client.post(
        f"/api/v1/mri/assessments/{assessment['id']}/clinical-context",
        headers={"Authorization": f"Bearer {token}"},
        json={"cyst_type": "IPMN", "clinical_context": {
            "evaluated_at": "2026-10-09T00:00:00Z", "assessment_date": "2026-10-09",
            "cyst_maximum_diameter": {"value_mm": 32, "unit": "mm", "source": "MRI report", "verification_status": "VERIFIED"},
            "mpd_diameter": {"value_mm": 6, "unit": "mm", "source": "MRI report", "verification_status": "VERIFIED"},
        }},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["guideline"]["assessment_status"] == "PARTIALLY_EVALUATED"
    assert body["clinical_context"]["cyst_maximum_diameter"]["status"] == "PRESENT"
    assert {item["rule_code"] for item in body["guideline"]["worrisome_features"]} >= {"WF-04", "WF-07"}
    assert "mpd_diameter_mm" not in body["guideline"]["missing_data"]
    assert body["trust"]["kyoto"]["wf_present"]
    assert body["trust"]["concordance"]["status"] == "REVIEW"
    assert body["trust"]["doctor_review_required"] is True


def test_non_ipmn_is_not_applicable_and_unknown_context_is_preserved(client):
    token = _token(client)
    assessment = _upload(client, token)["assessment"]
    response = client.post(
        f"/api/v1/mri/assessments/{assessment['id']}/clinical-context",
        headers={"Authorization": f"Bearer {token}"},
        json={"cyst_type": "NON_IPMN", "clinical_context": {"evaluated_at": "2026-10-09T00:00:00Z"}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["guideline"]["not_applicable"] is True
    assert body["guideline"]["assessment_status"] == "NOT_APPLICABLE"
    assert body["clinical_context"]["mpd_diameter"]["value_mm"] is None
    assert body["clinical_context"]["obstructive_jaundice"]["status"] == "UNKNOWN"


def test_numeric_measurement_can_be_explicitly_absent(client):
    token = _token(client)
    assessment = _upload(client, token)["assessment"]
    response = client.post(
        f"/api/v1/mri/assessments/{assessment['id']}/clinical-context",
        headers={"Authorization": f"Bearer {token}"},
        json={"cyst_type": "IPMN", "clinical_context": {
            "evaluated_at": "2026-10-09T00:00:00Z",
            "mpd_diameter": {"status": "ABSENT", "unit": "mm", "source": "Clinician review", "verification_status": "VERIFIED"},
        }},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["clinical_context"]["mpd_diameter"]["status"] == "ABSENT"
    assert body["clinical_context"]["mpd_diameter"]["value_mm"] is None
    assert "mpd_diameter_mm" not in body["guideline"]["missing_data"]


def test_assessment_records_are_persisted(client):
    token = _token(client)
    original = _upload(client, token)["assessment"]
    with client.app.state.test_session_factory() as db:
        stored = db.get(Assessment, original["id"])
        assert stored.guideline_result["guideline"]["version"] == "2024"
        assert stored.trust_result["trust_status"] == "INDETERMINATE"
        assert stored.explanation_result["provider"] == "DETERMINISTIC"
