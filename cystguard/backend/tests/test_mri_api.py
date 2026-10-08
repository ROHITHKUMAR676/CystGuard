import gzip
from pathlib import Path

from app.ml.ml_service import CystXMLService, MLPrediction, get_ml_service
from app.config import get_settings
from app.mri.models import Assessment, MRIStudy, MRIStudyStatus, PredictionStatus


def _nifti1_bytes() -> bytes:
    header = bytearray(348)
    header[:4] = (348).to_bytes(4, "little")
    header[344:348] = b"n+1\x00"
    return bytes(header) + b"\x00" * 16


def _doctor_token(client, email="doctor@example.test"):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-test-password"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class SuccessfulMLService:
    def __init__(self):
        self.paths = []

    def analyze(self, mri_path: Path):
        self.paths.append(Path(mri_path))
        return MLPrediction(
            model_id="cystx",
            model_version="cystx-baseline-v1",
            risk_class="HIGH_RISK",
            raw_score=0.6036,
            threshold=0.5,
        )


def _upload(client, token, filename="scan.nii.gz", content=None):
    content = gzip.compress(_nifti1_bytes()) if content is None else content
    headers = {"Authorization": f"Bearer {token}"} if token else None
    return client.post(
        "/api/v1/mri/studies",
        headers=headers,
        files={"upload": (filename, content, "application/octet-stream")},
    )


def test_unsupported_mri_extension_rejected(client, registered_user):
    token = _doctor_token(client)
    response = _upload(client, token, "scan.dcm", b"not a NIfTI")
    assert response.status_code == 415


def test_empty_and_invalid_nifti_uploads_rejected(client, registered_user):
    token = _doctor_token(client)
    empty = _upload(client, token, "empty.nii", b"")
    invalid = _upload(client, token, "invalid.nii", b"not a NIfTI image")
    assert empty.status_code == 422
    assert invalid.status_code == 422


def test_unauthenticated_upload_rejected(client):
    response = _upload(client, None)
    assert response.status_code == 401


def test_authenticated_upload_persists_study_and_successful_assessment(
    client, registered_user, mri_storage_dir
):
    token = _doctor_token(client)
    fake_ml = SuccessfulMLService()
    client.app.dependency_overrides[get_ml_service] = lambda: fake_ml

    response = _upload(client, token)
    assert response.status_code == 201
    body = response.json()
    assert body["mri_study"]["status"] == "ANALYZED"
    assert body["mri_study"]["original_filename"] == "scan.nii.gz"
    assert body["assessment"] == {
        **body["assessment"],
        "model_id": "cystx",
        "model_version": "cystx-baseline-v1",
        "architecture": "3D DenseNet-121",
        "risk_class": "HIGH_RISK",
        "raw_score": 0.6036,
        "threshold": 0.5,
        "prediction_status": "SUCCESS",
        "input_quality_status": "ACCEPTABLE",
        "fallback_used": False,
        "error_message": None,
    }
    assert "cancer_probability" not in body["assessment"]
    assert len(fake_ml.paths) == 1
    assert not fake_ml.paths[0].exists()  # Temporary inference copy was removed.

    study_id = body["mri_study"]["id"]
    assessment_id = body["assessment"]["id"]
    read_response = client.get(
        f"/api/v1/mri/studies/{study_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assessment_response = client.get(
        f"/api/v1/mri/assessments/{assessment_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert read_response.status_code == assessment_response.status_code == 200
    assert read_response.json()["assessment"]["id"] == assessment_id
    assert assessment_response.json()["prediction_status"] == "SUCCESS"

    with client.app.state.test_session_factory() as db:
        study = db.get(MRIStudy, study_id)
        assessment = db.get(Assessment, assessment_id)
        assert study is not None and study.status is MRIStudyStatus.ANALYZED
        assert assessment is not None and assessment.prediction_status is PredictionStatus.SUCCESS
        assert study.storage_key
        assert (mri_storage_dir / study.storage_key).is_file()
    assert "storage_key" not in body["mri_study"]
    client.app.dependency_overrides.pop(get_ml_service, None)


def test_model_failure_persists_failed_assessment_without_fake_prediction(
    client, registered_user
):
    token = _doctor_token(client)

    class FailingMLService:
        def analyze(self, mri_path):
            raise RuntimeError("private model traceback detail")

    client.app.dependency_overrides[get_ml_service] = lambda: FailingMLService()
    response = _upload(client, token)
    assert response.status_code == 201
    assessment = response.json()["assessment"]
    assert response.json()["mri_study"]["status"] == "FAILED"
    assert assessment["prediction_status"] == "FAILED"
    assert assessment["raw_score"] is None
    assert assessment["architecture"] == "3D DenseNet-121"
    assert assessment["risk_class"] is None
    assert "private model traceback" not in assessment["error_message"]
    client.app.dependency_overrides.pop(get_ml_service, None)


def test_checkpoint_configuration_failure_is_reported_without_prediction(
    client, registered_user, monkeypatch
):
    token = _doctor_token(client)
    settings = get_settings().model_copy(
        update={"cystx_checkpoint_path": None, "cystx_source_path": None}
    )
    client.app.dependency_overrides[get_ml_service] = lambda: CystXMLService(settings)
    response = _upload(client, token)
    assert response.status_code == 201
    assessment = response.json()["assessment"]
    assert assessment["prediction_status"] == "FAILED"
    assert assessment["raw_score"] is None
    assert assessment["error_message"] == "CYSTX_CHECKPOINT_PATH is not configured."
    client.app.dependency_overrides.pop(get_ml_service, None)


def test_user_cannot_read_another_doctors_mri_or_assessment(client, registered_user):
    owner_token = _doctor_token(client)
    fake_ml = SuccessfulMLService()
    client.app.dependency_overrides[get_ml_service] = lambda: fake_ml
    created = _upload(client, owner_token).json()
    client.app.dependency_overrides.pop(get_ml_service, None)

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "other-doctor@example.test", "password": "strong-test-password", "role": "DOCTOR"},
    )
    assert other.status_code == 201
    other_token = _doctor_token(client, "other-doctor@example.test")
    headers = {"Authorization": f"Bearer {other_token}"}
    study_response = client.get(f"/api/v1/mri/studies/{created['mri_study']['id']}", headers=headers)
    assessment_response = client.get(
        f"/api/v1/mri/assessments/{created['assessment']['id']}", headers=headers
    )
    assert study_response.status_code == 404
    assert assessment_response.status_code == 404


def test_patient_grant_controls_linked_mri_volume_and_revocation(
    client, registered_user, mri_storage_dir, tmp_path
):
    import nibabel as nib
    import numpy as np

    owner_token = _doctor_token(client)
    patient = client.post("/api/v1/auth/register", json={
        "email": "linked-mri-patient@example.test", "password": "strong-test-password",
        "role": "PATIENT", "doctor_access_code": registered_user["doctor_access_code"],
    })
    assert patient.status_code == 201
    patient_id = patient.json()["id"]
    patient_token = _doctor_token(client, "linked-mri-patient@example.test")
    owner_id = registered_user["id"]
    approved = client.post(f"/api/v1/patients/{patient_id}/doctors/{owner_id}/approve-access",
        headers={"Authorization": f"Bearer {owner_token}"})
    assert approved.status_code == 200

    volume_path = tmp_path / "small-volume.nii"
    nib.save(nib.Nifti1Image(np.arange(4 * 5 * 6, dtype=np.float32).reshape(4, 5, 6), np.eye(4)), volume_path)
    fake_ml = SuccessfulMLService()
    client.app.dependency_overrides[get_ml_service] = lambda: fake_ml
    uploaded = client.post("/api/v1/mri/studies", headers={"Authorization": f"Bearer {owner_token}"},
        data={"patient_id": str(patient_id)},
        files={"upload": ("small-volume.nii", volume_path.read_bytes(), "application/octet-stream")})
    client.app.dependency_overrides.pop(get_ml_service, None)
    assert uploaded.status_code == 201, uploaded.text
    study_id = uploaded.json()["mri_study"]["id"]
    assessment_id = uploaded.json()["assessment"]["id"]

    other = client.post("/api/v1/auth/register", json={
        "email": "granted-mri-doctor@example.test", "password": "strong-test-password", "role": "DOCTOR",
    })
    assert other.status_code == 201
    other_token = _doctor_token(client, "granted-mri-doctor@example.test")
    requested = client.post("/api/v1/patients/access-requests",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"doctor_access_code": other.json()["doctor_access_code"]})
    assert requested.status_code == 201
    approved = client.post(f"/api/v1/patients/{patient_id}/doctors/{other.json()['id']}/approve-access",
        headers={"Authorization": f"Bearer {other_token}"})
    assert approved.status_code == 200

    headers = {"Authorization": f"Bearer {other_token}"}
    assert client.get(f"/api/v1/mri/studies/{study_id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/mri/assessments/{assessment_id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/mri/studies/{study_id}/volume", headers=headers).status_code == 200
    slice_response = client.get(f"/api/v1/mri/studies/{study_id}/volume/axial/0.png", headers=headers)
    assert slice_response.status_code == 200
    assert slice_response.headers["content-type"] == "image/png"

    revoked = client.post(f"/api/v1/patients/{patient_id}/doctors/{other.json()['id']}/revoke",
        headers={"Authorization": f"Bearer {patient_token}"})
    assert revoked.status_code == 200
    assert client.get(f"/api/v1/mri/studies/{study_id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/mri/studies/{study_id}/volume", headers=headers).status_code == 404
    # The still-connected uploader retains access until their own grant is revoked.
    assert client.get(f"/api/v1/mri/studies/{study_id}",
        headers={"Authorization": f"Bearer {owner_token}"}).status_code == 200
    revoked_owner = client.post(f"/api/v1/patients/{patient_id}/doctors/{owner_id}/revoke",
        headers={"Authorization": f"Bearer {patient_token}"})
    assert revoked_owner.status_code == 200
    assert client.get(f"/api/v1/mri/studies/{study_id}",
        headers={"Authorization": f"Bearer {owner_token}"}).status_code == 404
