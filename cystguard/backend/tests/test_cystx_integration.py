import importlib.util
import os
from pathlib import Path

import pytest

from app.config import get_settings

settings = get_settings()
test_mri_path = os.getenv("CYSTGUARD_TEST_MRI_PATH")
missing_runtime = [name for name in ("torch", "monai") if importlib.util.find_spec(name) is None]
missing_configuration = []
if not test_mri_path or not Path(test_mri_path).is_file():
    missing_configuration.append("CYSTGUARD_TEST_MRI_PATH (valid local T1 NIfTI file)")
if settings.cystx_checkpoint_path is None or not settings.cystx_checkpoint_path.is_file():
    if "CYSTX_CHECKPOINT_PATH (local Cyst-X checkpoint)" not in missing_configuration:
        missing_configuration.append("CYSTX_CHECKPOINT_PATH (local Cyst-X checkpoint)")
if settings.cystx_source_path is None or not settings.cystx_source_path.is_dir():
    missing_configuration.append("CYSTX_SOURCE_PATH (official Cyst-X source directory)")
if missing_runtime:
    missing_configuration.append(f"runtime packages: {', '.join(missing_runtime)}")
skip_reason = (
    "Missing real Cyst-X smoke-test requirements: " + "; ".join(missing_configuration)
    if missing_configuration
    else None
)


@pytest.mark.integration
@pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "Cyst-X integration is not configured.")
def test_real_cystx_inference_through_authenticated_backend(client, registered_user):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "strong-test-password"},
    ).json()["access_token"]
    path = Path(test_mri_path)
    with path.open("rb") as mri_file:
        response = client.post(
            "/api/v1/mri/studies",
            headers={"Authorization": f"Bearer {token}"},
            files={"upload": (path.name, mri_file, "application/octet-stream")},
        )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["mri_study"]["status"] == "ANALYZED"
    assert payload["assessment"]["prediction_status"] == "SUCCESS"
    assert payload["assessment"]["model_id"] == "cystx"
    assert payload["assessment"]["risk_class"] in {"HIGH_RISK", "NO_LOW_RISK"}
    assert isinstance(payload["assessment"]["raw_score"], (int, float))
