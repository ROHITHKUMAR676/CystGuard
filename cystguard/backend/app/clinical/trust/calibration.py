from app.clinical.trust.schemas import CalibrationResult, CalibrationStatus


def calibration_unavailable(model_version: str) -> CalibrationResult:
    """Return explicit unavailable status; never fit or synthesize calibration."""
    return CalibrationResult(available=False, model_version=model_version, status=CalibrationStatus.NOT_CALIBRATED)
