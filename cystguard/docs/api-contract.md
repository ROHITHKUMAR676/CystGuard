# Shared API contract

Authoritative contract between frontend and backend. Frontend never guesses backend data. Backend never assumes frontend requirements. Both follow the shared API contract.

## Phase 1 endpoints

All endpoints use the `/api/v1` prefix.

| Method | Path | Request | Response | Authentication |
|---|---|---|---|---|
| GET | `/health` | None | `{ "status": "ok", "version": string }` | Public |
| POST | `/auth/register` | `{ "email": string, "password": string, "role": "DOCTOR" or "PATIENT", "display_name"?: string, "doctor_access_code"?: string }` | User response including `display_name`; clinician responses include their generated `doctor_access_code` | Public |
| POST | `/auth/login` | `{ "email": string, "password": string }` | `{ "access_token": string, "token_type": "bearer", "expires_in": integer }` | Public |
| GET | `/auth/me` | Bearer access token | User response shown above | Required |

Registration normalizes email, requires a password of at least 10 characters, and rejects duplicate addresses with HTTP 409. Clinician accounts receive a generated access code. Patient registration may include a clinician access code, which creates a `PENDING` relationship; an invalid code returns HTTP 422. A patient can register without a clinician code and use their own patient workspace immediately. Login failures and missing/invalid bearer tokens return HTTP 401. Password hashes are never returned.

`GET /health` is a lightweight liveness check and retains its `{ status, version }` response without querying persistence. Authenticated `GET /health/database` performs a minimal database connectivity check and returns `{ "database": "connected" }`; failures return a safe unavailable response without exposing connection details.

## Phase 2 MRI endpoints

All endpoints use the `/api/v1` prefix. MRI routes require a bearer token for a `DOCTOR` user. Unlinked studies are owner-only; patient-linked studies and their assessments/volumes require the patient’s active grant to the doctor.

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/mri/studies` | Multipart form field `upload`, containing one `.nii` or `.nii.gz` file | `MRIAnalysisResponse` below; HTTP 201 when study and assessment records are created, including an inference-failure assessment |
| GET | `/mri/studies/{study_id}` | None | `MRIAnalysisResponse` for an owned unlinked study or a patient-linked study with active grant |
| GET | `/mri/assessments/{assessment_id}` | None | Assessment for a study owned by the caller |
| POST | `/mri/assessments/{assessment_id}/clinical-context` | `{ cyst_type, clinical_context: ClinicalContext }` | Persists submitted facts, evaluates the existing Kyoto engine and trust/concordance services, returns the updated assessment |
| POST | `/mri/assessments/{assessment_id}/explanation` | None | Regenerates a structured explanation from saved facts; uses Sarvam when configured, otherwise returns a deterministic explanation |
| GET | `/mri/studies/{study_id}/volume` | None | Authenticated MRI dimensions, voxel spacing, planes and explicit no-overlay metadata |
| GET | `/mri/studies/{study_id}/volume/{plane}/{index}.png` | None | Authenticated PNG slice from the stored study volume |

Unsupported formats return HTTP 415; empty, malformed NIfTI, or missing filenames return HTTP 4xx; over-limit files return HTTP 413. `MAX_MRI_UPLOAD_SIZE_MB` configures the size limit (default 512). Uploads validate extension, size, and NIfTI header/magic. This is technical input validation only and does not assess clinical MRI quality. Uploaded file data is stored outside the repository; storage keys and filesystem paths are never returned.

### MRI analysis response

The response contains `mri_study` (`id: string`, `original_filename: string`, `modality: string`, `file_format: NIFTI | NIFTI_GZ`, `uploaded_at: datetime`, `status: UPLOADED | PROCESSING | ANALYZED | FAILED`, `error_message: string | null`) and `assessment` (`id: string`, `mri_study_id: string`, `model_id: string`, `model_version: string`, `architecture: string | null`, `risk_class: string | null`, `raw_score: number | null`, `threshold: number | null`, `prediction_status: SUCCESS | FAILED`, `input_quality_status: ACCEPTABLE | NOT_EVALUATED`, `fallback_used: boolean`, `error_message: string | null`, `created_at: datetime`).

`risk_class` preserves the current adapter profiles `HIGH_RISK` and `NO_LOW_RISK`. `raw_score` is the model's sigmoid score, not a calibrated cancer or malignancy probability. `ACCEPTABLE` means only that the upload passed configured technical checks. If model configuration or inference fails, the study and assessment are persisted with `FAILED`, null score/profile/threshold, and a safe error message; no prediction is fabricated. `fallback_used` is false because no fallback model exists.

Assessment responses additionally contain persisted `clinical_context`, `guideline`, `trust`, and `explanation` fields. Upload-created clinical context defaults to UNKNOWN and runs the existing Kyoto 2024 evaluator and TrustService. A doctor may submit reviewed structured clinical facts; absent or omitted fields stay UNKNOWN. `NON_IPMN` makes Kyoto NOT_APPLICABLE. Trust and concordance use the existing service schemas; uncertainty remains NOT_CALIBRATED and calibration remains NOT_CALIBRATED unless validated artifacts exist. Sarvam is an optional explanation layer, never a clinical decision dependency. `SARVAM_API_KEY` is server-side only. Explanation failures return a validated deterministic explanation. No segmentation mask is produced by the Cyst-X classifier; volume endpoints expose slices only.

The Cyst-X checkpoint path and official source directory are configured through `CYSTX_CHECKPOINT_PATH` and `CYSTX_SOURCE_PATH`; model weights are not stored in Git or downloaded at startup. `CYSTX_MODEL_VERSION` sets the reported version.

## Phase 5 report and medication OCR

These synchronous endpoints require a bearer token. They accept PDF, PNG, JPEG, TIFF, or BMP uploads using multipart field `upload`, with a default 25 MB limit (`MAX_DOCUMENT_UPLOAD_SIZE_MB`). Extension and file signature are checked. Responses contain candidate extraction and an `UNVERIFIED` status; OCR does not make clinical findings or medication changes. Raw and normalized text are retained. The document ID is also the synchronous OCR job ID. Opaque storage keys and local paths are never returned.

| Method | Path | Purpose / access |
|---|---|---|
| POST | `/reports/documents` | Upload and extract report; authenticated uploader |
| GET | `/reports` | List reports uploaded by the authenticated user |
| GET | `/reports/ocr/{document_id}` | Read report OCR job/result; document owner only |
| GET | `/reports/{report_id}` | Read extracted report; report or source document ID; owner only |
| POST | `/reports/{report_id}/verify` | Doctor verifies/corrects extracted fields; doctor must own the document |
| POST | `/medications/documents` | Upload and extract medication document; authenticated uploader |
| GET | `/medications/ocr/{document_id}` | Read medication OCR result; document owner only |
| GET | `/patients/{patient_id}/medications` | List extracted medication candidates; patient self or a doctor with an active approved patient grant |
| POST | `/medications/{medication_id}/verify` | Doctor verifies/corrects own record or patient-linked record with active patient grant; lifecycle status changes only when explicitly supplied |
| POST | `/patients/{patient_id}/medications/{medication_id}/review-conflict` | Patient reviews a conflict on their own record with a note; does not choose a winner or change medication status |

Report upload/read responses use `MedicalReportRead`: `{ id, document, fields, verified_fields }`. `document` includes its ID, type, safe original filename, media type, extraction/verification statuses, method, page count, optional extraction confidence, raw OCR text, normalized text, and extraction/verification timestamps. `fields` maps field names to `{ value, normalized_value, status: PRESENT | UNKNOWN, extraction_confidence, provenance, needs_verification, normalization_notes }`. Provenance includes source document ID/type, optional page and excerpt, method, and optional extraction confidence. `verified_fields` is null until review, then stores the human-reviewed overlay separately from immutable candidates.

Medication upload/read responses use `MedicationOCRRead`: `{ document, medications }`. Each candidate includes its ID, optional patient ID, source document ID/type, immutable `extracted_fields`, optional `verified_fields`, verification status, lifecycle status, confidence, page/source excerpt, note, timestamps, and any conflict records. Conflict records include both source record IDs, differing explicit fields, `CONFLICT_REQUIRES_REVIEW | REVIEWED`, optional selected resolution source, review timestamp, and note. A document with no detectable medication candidates returns an empty `medications` list; no medication is inferred from image appearance alone.

Report verification accepts `{ "fields": { ... }, "doctor_note": string | null }`; verified values are stored separately from immutable extracted candidates. Medication verification accepts `{ "fields": { ... }, "medication_status": "UNKNOWN" | "ACTIVE" | "HISTORICAL" | "ENDED" | "DISCONTINUED" | null, "doctor_note": string | null }`. Medication conflict review accepts `{ "review_note": string, "resolution_record_id": string }`; the selected source is recorded and neither record nor lifecycle status is automatically changed. Unset medication status remains `UNKNOWN`; omission from another document never implies discontinuation.

OCR provenance includes source document ID, source excerpt, extraction method, page when available, and extraction confidence when the provider supplies it. `extraction_confidence` is not clinical confidence. Reports and medication candidates remain unverified until the relevant human review endpoint is used. No endpoint maps OCR content to Kyoto rules.

Documents remain scoped to their authenticated uploader. Patient medication listing and conflict review are self-only. A doctor may verify a patient-linked medication record after that patient grants the doctor access; OCR documents and report reads remain uploader-scoped. The optional `backend/requirements-ocr.txt` provides pypdf/PyMuPDF/Pillow/pytesseract; image and scanned-PDF OCR require a local Tesseract executable. Missing runtime returns HTTP 503. Invalid signatures return HTTP 422, unsupported extensions HTTP 415, oversize documents HTTP 413, and unauthorized cross-user reads HTTP 404/403 as documented by endpoint role.

For optional real inference, install the standard backend requirements and `backend/requirements-ml.txt`, provide those two Cyst-X paths and a local test file through `CYSTGUARD_TEST_MRI_PATH`, then run `python -m pytest tests/test_cystx_integration.py -q` from `backend/`. The integration test sends the file through the authenticated HTTP upload path. It skips when any local model dependency is missing.

Backend schemas: `backend/app/schemas/`. Frontend types: `frontend/src/types/`.

Every contract change updates (1) backend schema, (2) frontend type when applicable, (3) this document, (4) affected tests, and (5) `change-log.md`. Do not silently rename fields.

## Phase 6 longitudinal MRI and surveillance

Patient-linked MRI history is available only after the patient requests access and that doctor approves it. `POST /patients/{patient_id}/doctors/{doctor_id}/access` and `POST /patients/access-requests` create pending relationships; `POST /patients/{patient_id}/doctors/{doctor_id}/approve-access` activates a pending relationship, and `/decline-access` declines it. Patients can revoke an active relationship through `/revoke`. Doctors can link a new upload using multipart `patient_id` and an explicit `study_date`. Existing uploads remain unlinked. Upload timestamps are never substituted for study dates.

| Method | Path | Purpose / access |
|---|---|---|
| GET | `/patients/{patient_id}/mri/timeline` | Patient self or doctor with active grant; explicit study dates order records; `ordering_complete` signals missing dates |
| GET | `/patients/{patient_id}/mri/compare?previous_study_id=...&current_study_id=...` | Authorized two-study factual comparison |
| GET | `/mri/studies/{study_id}/changes?previous_study_id=...` | Authorized factual comparison for same linked patient |
| POST | `/mri/studies/{study_id}/measurements` | Owning doctor records sourced, optionally verified structured measurement/finding |
| GET/POST | `/patients/{patient_id}/surveillance` | Patient/authorized doctor read; authorized doctor creates clinician-defined plan |
| GET | `/patients/{patient_id}/surveillance/{plan_id}` | Patient self or doctor with active grant; includes events |
| POST | `/patients/{patient_id}/surveillance/{plan_id}/complete` | Authorized doctor marks plan complete |
| POST | `/patients/{patient_id}/surveillance/{plan_id}/events` | Authorized doctor adds follow-up event |
| POST | `/patients/{patient_id}/surveillance/{plan_id}/events/{event_id}/complete` | Authorized doctor records completion |
| GET | `/patients/access-requests` | Doctor lists their pending and active patient relationships |
| GET | `/patients/directory` | Doctor lists patients with active relationships only |
| POST | `/patients/access-requests/invite` | Doctor creates a pending request for an existing patient account by email |

Measurements preserve source, source type, explicit date, unit, verification, and comparability. Only verified comparable diameters with valid ordered dates and mm/cm units yield change and annualized rate. Missing inputs return `INSUFFICIENT_DATA`/`NOT_CALCULABLE`; incompatible data return `INCOMPARABLE`. Findings propagate UNKNOWN. These observational summaries do not generate diagnoses or Kyoto evaluations. Historical assessments are retained; raw scores are not probabilities. Surveillance plans/events are append-only clinician-owned records; date status is PLANNED before target, DUE on target, OVERDUE after target, with completed/cancelled terminal statuses. No AI output schedules follow-up.

## Phase 7 patient workflow and CareLoop

All endpoints use `/api/v1`. Patients can use their own patient records without a clinician relationship. Doctors require an active, doctor-approved patient relationship to access that patient's clinical data. Clinician-only notes are omitted from patient note listings. Patient-entered symptom and meal content remains reported information and is never converted into a diagnosis or Kyoto fact.

| Method | Path | Purpose / access |
|---|---|---|
| GET | `/patients/{patient_id}/care-profile` | Patient self or authorized doctor; compact summary of existing records and explicit missing states |
| POST/GET | `/patients/{patient_id}/symptoms` | Patient creates; patient or authorized doctor reads |
| PATCH | `/patients/{patient_id}/symptoms/{symptom_id}` | Patient edits own report; authorized doctor records review metadata only |
| POST/GET | `/patients/{patient_id}/notes` | Patient or authorized doctor creates notes; clinician-only notes are doctor-visible only |
| GET | `/patients/{patient_id}/careloop` | Patient self or authorized doctor; chronological event references |
| GET/POST | `/patients/{patient_id}/meals` | Patient self creates text-only entries; patient or authorized doctor reads meal records |
| GET/POST | `/patients/{patient_id}/messages` | Patient self or connected doctor reads/writes care-team messages; patient sending requires an active doctor connection |
| GET | `/patients/{patient_id}/visit-preparation` | Authorized doctor; structured aggregation with absent persisted domains marked UNKNOWN |
| GET/POST | `/patients/{patient_id}/reviews` | Authorized doctor lists/creates workflow review items |
| POST | `/patients/{patient_id}/reviews/{review_id}/resolve` | Authorized doctor resolves/dismisses with note; resolution metadata is retained |

Symptoms, meals, messages, and notes are authored, timestamped records; free text is not parsed into clinical facts. Symptom entry creates a normal-priority workflow review item, not an alert or diagnosis. Text-only meal entries store the patient's description. Photo-based analysis, estimates, patient confirmation, and nutrition monitoring use the endpoints below. CareLoop records references and workflow events; it does not recommend care. Visit preparation does not infer Kyoto/trust results or a diagnosis. Persisted Kyoto/trust assessments remain unavailable and are returned as UNKNOWN. Review queue items are clinician workflow records; no priority is assigned from a model score.

## Meal analysis and nutrition monitoring

| Method | Path | Purpose / access |
|---|---|---|
| POST | `/food/meals/analyze` | Patient uploads a meal image for FoodCNN image-level nutrient/portion estimates; estimate starts awaiting confirmation |
| POST | `/food/meals/{meal_id}/confirm` | Patient confirms/corrects the estimate or marks it uncertain |
| PATCH | `/food/meals/{meal_id}` | Patient corrects a confirmed meal while preserving provider output and correction history |
| GET | `/food/meals/{meal_id}/image` | Patient or doctor with active grant streams the stored image |
| GET | `/patients/{patient_id}/nutrition/summary` | Patient self or doctor with active grant reads daily estimates, patient-reported observations, recorded target, and monitoring flags |
| POST | `/patients/{patient_id}/nutrition/observations` | Patient records own weight, appetite, reported symptoms, and intake-log completion |
| POST | `/patients/{patient_id}/nutrition/profile` | Doctor with active grant records clinician-entered nutrition targets/context |

FoodCNN produces image-level calorie, macronutrient, and portion estimates. It does not return food labels or recognition confidence; food items are patient-entered and confidence remains unavailable. Pending or uncertain estimates remain visible but do not contribute to nutrition totals. Targets are never generated automatically. See [meal analysis and nutrition monitoring](food-analysis.md) for the provider, provenance, and monitoring limits.

## Frontend route-to-API mapping

The active frontend is a single-page portal using the existing client-side page state in `frontend/src/main.js`; shared network handling, typed domain clients, and response types live in `frontend/src/services/api.ts` and `frontend/src/types/`. The frontend does not use a separate router framework.

| Frontend flow | Backend calls | Status / constraint |
|---|---|---|
| Sign in and registration | `POST /auth/login`, `POST /auth/register`, `GET /auth/me` | Connected; backend role is authoritative |
| Patient care workspace and access request | `GET /patients/{id}/care-profile`, `GET/POST /patients/access-requests`, `GET /patients/{id}/access-requests` | Connected; patient tabs work without clinician approval |
| Clinician dashboard, directory, and access decisions | `GET /patients/access-requests`, `GET /patients/directory`, `GET /patients/{id}/reviews`, `GET /patients/{id}/surveillance`, `POST .../approve-access`, `POST .../decline-access` | Connected; clinical data requires an active grant |
| MRI upload and model result | `POST /mri/studies`, `GET /mri/studies/{id}`, `GET /mri/assessments/{id}` | Connected; frontend accepts `.nii` only; backend contract continues to accept `.nii` and `.nii.gz` |
| Clinical review | `POST/GET /patients/{id}/notes`, `POST/GET /patients/{id}/reviews` | Clinician notes and workflow review items persist; structured facts and deterministic guideline/trust/concordance outputs persist on MRI assessments |
| Guideline, trust, and concordance cards | `POST /mri/assessments/{id}/clinical-context`, `GET /mri/studies/{id}`, `GET /mri/assessments/{id}` | Connected; omitted clinical facts remain UNKNOWN; calibration stays unavailable without validated artifacts |
| MRI timeline and comparison | `GET /patients/{id}/mri/timeline`, `GET /patients/{id}/mri/compare` | Connected for stored studies and sourced measurements |
| Surveillance | `GET/POST /patients/{id}/surveillance`, plan completion endpoint | Connected; schedule is clinician-entered |
| Reports | `POST /reports/documents`, `GET /reports`, `GET /reports/patients/{id}`, `GET /reports/{id}`, `POST /reports/{id}/verify` | Patient-uploaded reports are visible to the patient and doctors with an active grant; clinician report uses browser print preview; no backend PDF generator |
| Medication OCR and review | `POST /medications/documents`, `GET /medications/ocr/{id}`, `GET /patients/{id}/medications`, `POST /medications/{id}/verify`, patient conflict review endpoint | Connected; doctor list/verification requires active grant; OCR documents remain uploader-owned |
| Symptoms, meals, CareLoop, visit questions, messages | `/patients/{id}/symptoms`, `/meals`, `/careloop`, `/notes`, `/messages` | Connected; records persist with their authorship and confirmation state |
| Meal photo analysis and nutrition | `/food/meals/analyze`, `/food/meals/{id}/confirm`, `/patients/{id}/nutrition/summary`, `/patients/{id}/nutrition/observations`, `/patients/{id}/nutrition/profile` | Connected; image-level regression estimates require patient confirmation; no food labels or recognition confidence |
| Notifications | No notification endpoint is registered | Not available as a persisted notification feed |

Kyoto, trust, and concordance results are persisted with MRI assessments after clinician-submitted context is evaluated. Meal image analysis returns clearly labeled estimates from the configured food analysis provider; patients must confirm entries, and estimates are not clinical advice. The Cyst-X classifier does not produce validated lesion segmentation; volume endpoints expose slices only.
