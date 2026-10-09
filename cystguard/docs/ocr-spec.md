# Medical report OCR

## Purpose and provider

Report OCR is a document extraction and review workflow. It does not diagnose, interpret a missing finding as negative, or recommend treatment. `OCRProvider` is injectable; the local provider uses pypdf for selectable PDF text and local Tesseract for images and scanned PDF pages. Install Python dependencies with `pip install -r backend/requirements.txt`. Image and scanned-PDF OCR additionally require the Tesseract executable; install it for the operating system and set `TESSERACT_CMD` in the root `.env` if it is not on `PATH`.

Accepted file signatures are PDF, PNG, JPEG, TIFF, and BMP, with a 25 MB default limit controlled by `MAX_DOCUMENT_UPLOAD_SIZE_MB`. PDF processing is limited to 100 pages. Encrypted PDFs are rejected. API upload is synchronous. Each stored document is also its OCR job identifier.

## Extraction and record lifecycle

The service validates file extension and signature, invokes the provider, stores the original bytes through the storage abstraction, and persists both the provider's raw text and a whitespace-normalized copy. Candidate report fields include document type, patient identifiers when labeled, report/study dates, modality, body region, findings, impression, cyst size/location, MPD measurement, and explicit mentions of mural nodules, solid components, wall and duct findings. Extraction is deliberately conservative and regex based; unrecognized layouts remain null/`UNKNOWN`. Raw OCR text remains available with every result.

Each populated field retains the source document ID, page when available, source excerpt, extraction method, and provider extraction confidence when available. This is transcription confidence only, not clinical confidence. If the provider cannot report confidence, the value is null. Every candidate requires verification. The stored extracted fields remain unchanged; a doctor verification creates a separate verified-fields overlay and audit event. The local provider rejects encrypted, unreadable, and over-limit PDFs rather than silently treating them as empty; scanned pages are rendered and OCR'd locally when embedded text is sparse.

OCR output remains `UNVERIFIED` until an authenticated doctor verifies it. Even verified OCR data is not automatically converted to Kyoto facts in this phase. Later clinical integration must consume only a clinician-verified structured representation and preserve provenance.

## Access and limits

Documents are scoped to the authenticated uploader. Cross-user reads return not found. This repository has no doctor–patient relationship model yet, so a doctor cannot read a patient's separately uploaded document; sharing must wait for an authorized relationship implementation. Files are stored outside source directories and opaque storage keys are not returned. Verification audit records store actor, action, resource ID, and small nonclinical metadata, never raw OCR text.

The parser is not a general medical NLP system. It can miss fields, misread OCR, and produce incomplete or incorrect candidates. A human must compare extracted values with the original document.
