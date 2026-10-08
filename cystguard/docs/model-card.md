# Model card

## Model identity and intended use

CystGuard integrates the Cyst-X pretrained baseline as a research MRI risk-profiling component to support clinician review. It reports its model identity/version, `HIGH_RISK` or `NO_LOW_RISK` class, raw sigmoid score, and decision threshold. It is not an autonomous diagnostic or treatment system.

## Score interpretation

The raw sigmoid score is not a calibrated cancer probability. The current CystGuard baseline does not claim calibrated confidence or predictive uncertainty. The optional `DECISION_MARGIN` is the absolute distance from the configured class threshold and must not be interpreted as probability or confidence. The trust layer currently reports calibration as unavailable (`NOT_CALIBRATED`) and emits no calibrated score.

## Validation and limitations

No independent clinical validation, calibration study, or claim of clinical performance is documented for this integration. Independent patient-level and cross-center validation is required before making performance or calibrated-probability claims. Model output is an independent evidence stream; the trust layer compares it with structured Kyoto evidence and may flag review or discordance. Neither output is replaced by that comparison.

Model weights and patient data must not be committed to the repository.
