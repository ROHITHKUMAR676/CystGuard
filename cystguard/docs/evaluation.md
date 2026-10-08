# Evaluation and trust interpretation

## Current Cyst-X output

CystGuard exposes the Cyst-X baseline's `HIGH_RISK` / `NO_LOW_RISK` classification, raw sigmoid score, configured threshold, and model version. The raw score is a model output, not a calibrated cancer probability. No calibration dataset or validated mapping is currently configured, so `calibration.available` is false, `calibration.status` is `NOT_CALIBRATED`, and no calibrated score is emitted. The decision margin is `abs(raw_score - threshold)` and is labeled `DECISION_MARGIN`; it is only distance from the classification threshold, not confidence, probability, or clinical certainty. At the threshold, the margin is zero; the trust layer preserves the supplied risk class and does not independently reclassify it.

## Uncertainty limitations

No validated predictive uncertainty method is available. The current result reports `NOT_CALIBRATED` and `UNCERTAINTY_UNAVAILABLE`; it does not claim Bayesian uncertainty, confidence intervals, calibrated confidence, or predictive uncertainty.

## Kyoto evidence interpretation

The trust layer consumes an existing Kyoto assessment and does not run Kyoto rules. Any triggered HRS yields `HIGH_RISK_EVIDENCE`; absent HRS with a triggered WF yields `WORRISOME_EVIDENCE`; no triggered HRS/WF with no missing/not-evaluable rules yields `LOWER_RISK_EVIDENCE`. If no rule is triggered but any rule is not evaluable or has missing data, Kyoto is `INDETERMINATE`. UNKNOWN is never treated as ABSENT. An HRS or WF finding can be reported even when unrelated rules are unresolved; the missing information remains attached to the trust result and requires review.

## Concordance methodology

The service compares the Cyst-X class to the independent Kyoto evidence category:

| AI output | Kyoto evidence | Trust status |
|---|---|---|
| `HIGH_RISK` | HRS present | `CONCORDANT_HIGH` |
| `NO_LOW_RISK` | Complete lower-risk evidence | `CONCORDANT_LOWER` |
| Either class | WF only | `REVIEW` |
| `HIGH_RISK` | Complete lower-risk evidence | `DISCORDANT` |
| `NO_LOW_RISK` | HRS present | `DISCORDANT` |
| Either class | Kyoto indeterminate | `INDETERMINATE` |
| AI classification unavailable | Any Kyoto evidence | `INDETERMINATE` |

Discordance means the independent evidence streams differ and clinician review is warranted; it does not establish that either stream is wrong. WF-only evidence is not forced into binary agreement. `doctor_review_required` is a workflow flag, not a diagnosis or treatment recommendation. HRS presence also requires doctor review.

Each result retains model ID/version and supplied risk class, Kyoto guideline ID/version, trust engine name/version, evaluation timestamp, and deterministic reason codes. Calibration metadata can be passed through only when marked available with method, dataset, matching model version, and score; the trust layer does not fit or invent calibration. The result is a comparison artifact and does not modify either source assessment.

## Validation limits

These deterministic status rules are software behavior, not evidence of clinical performance. No independent patient-level or cross-center validation, discrimination assessment, or calibration study is claimed here. Any future calibration requires a properly separated, representative validation dataset and documented method/version. The service does not diagnose cancer, estimate cancer probability, or recommend treatment or surgery.
# Phase 6 evaluation boundary

Longitudinal calculations are deterministic data transformations, not validated clinical outcome predictions. Raw score trajectories are retained without probability interpretation. Missing dates, unverified values, or incompatible units must not produce a growth estimate. Surveillance date status uses the target date and current date; no follow-up interval is inferred from model output.

## Phase 7 workflow aggregation

Care profiles, visit-preparation summaries, CareLoop events, and review items are workflow/aggregation features, not clinical prediction outputs. They surface persisted records. Meal nutrition estimates and clinician-submitted Kyoto/trust assessment results are persisted with explicit provenance/status; they are not silently inferred from unrelated records. Review priority is user/workflow-supplied and is not derived from Cyst-X output.
