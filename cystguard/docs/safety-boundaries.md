# Safety boundaries

- CystGuard is decision support, not autonomous diagnosis.
- It does not replace radiologists or clinicians.
- It does not autonomously prescribe medication.
- Medication OCR extracts/documents information; it does not prescribe, change, or discontinue medication.
- OCR extraction confidence describes text extraction only and is not clinical confidence.
- Unverified OCR candidates never become Kyoto findings or other clinical truth automatically.
- OCR-based medication conflicts preserve all candidate records and require human review; review does not select a medication or change status by itself.
- CystGuard does not identify medications from pill appearance alone.
- FoodCNN provides image-level nutrient/portion estimates only; it does not identify food labels or return calibrated recognition confidence. Patient-entered food names and patient confirmation/corrections remain distinct from model output.
- Pending or uncertain meal estimates are excluded from nutrition totals. Recorded totals are not complete intake unless the patient reports that the log is complete.
- Only a clinician may enter an individualized nutrition target; CystGuard does not generate targets or universal forbidden-food rules.
- Nutrition flags are monitoring prompts for clinician/dietitian review, not diagnoses, treatment, PERT/medication changes, or assertions that a food caused a symptom.
- BMI and weight change are context requiring clinical interpretation, not diagnoses.
- Uncertainty must not be hidden.
- AI/guideline disagreement must be surfaced.
- Missing data must not be silently fabricated.
- Kyoto 2024 assessment is specifically for IPMN-related risk assessment.
- Research benchmark metrics must never be presented as CystGuard clinical performance.

Safety implementation details will be filled progressively. No clinical validation or regulatory approval is claimed.
# Longitudinal and surveillance boundaries

MRI change does not imply malignancy. Growth at any rate is not a diagnosis and does not itself trigger treatment. Surveillance plans and follow-up dates are explicitly entered by an authorized clinician; no AI score creates or changes a plan. Historical assessments and plans are preserved.

## Patient workflow and CareLoop

Symptoms are patient-reported observations, not diagnoses or presumed cyst-related findings. Notes remain authored documentation and are never automatically interpreted as structured clinical facts. CareLoop is a workflow timeline, and visit preparation is an aggregation of stored records; neither generates diagnoses or treatment/medication/surgery recommendations. Missing persisted data remains UNKNOWN or PENDING_REVIEW. Cyst-X raw scores remain non-probabilistic.
