from app.clinical.trust.schemas import UncertaintyStatus, UncertaintyView


def unavailable_uncertainty() -> UncertaintyView:
    """No validated uncertainty method is configured for this baseline."""
    return UncertaintyView(status=UncertaintyStatus.NOT_CALIBRATED, reason_codes=("UNCERTAINTY_UNAVAILABLE",))
