# Medication OCR

## Scope and provider

Medication OCR extracts candidate medication strings from uploaded prescription images/PDFs, discharge medication lists, medication lists, and readable labels. It does not identify pills from shape/color, prescribe, recommend dosage, diagnose, or automatically change a medication. It uses the shared injectable OCR provider described in [ocr-spec.md](ocr-spec.md); tests inject a deterministic local fake.

The initial candidate parser only accepts explicit medication/name labels or lines containing a recognizable strength. It can extract explicitly printed name, generic/brand label, strength, dose, form, frequency, route, labeled start/end dates, duration, prescriber, and indication. It uses no medication catalog and does not infer missing values. Normalization is limited to unambiguous strength unit conversion, common frequency wording, dosage-form aliases, and explicit route aliases. Uncertain normalization retains the source string and a note for review.

Every medication candidate preserves raw source text, document ID, page when available, extraction method, and extraction confidence when available. Confidence describes extraction only, never clinical correctness. Original extracted fields are retained separately from clinician-verified overlays.

## Review and lifecycle

New candidates start `UNVERIFIED` with medication lifecycle `UNKNOWN`. An authenticated doctor who owns the source document may verify/correct fields and may explicitly set `ACTIVE`, `HISTORICAL`, `ENDED`, or `DISCONTINUED`. No lifecycle state is inferred from a medication being absent in a later document. Verification creates an audit event.

Conflicts are detected for same-name medication records belonging to the same patient's account when explicit strength, dose, form, frequency, or route values disagree. Both source records and conflicting values remain stored. The patient can explicitly select one source record as the resolved source and provide a note; this is persisted as a review decision, does not delete either source, and does not alter lifecycle status. Doctor access and conflict review are scoped by the active doctor–patient grant.

## Access and limitations

Patient medication listing is restricted to the authenticated patient whose ID appears in the path or a doctor with an active grant. Patient-uploaded records can be verified by an authorized doctor. Doctor-uploaded records remain unassigned because the upload route does not accept a patient ID. The parser is conservative and incomplete, and OCR candidates always require human review before being relied on.
