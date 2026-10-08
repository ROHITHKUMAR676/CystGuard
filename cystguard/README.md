# CystGuard

AI-assisted pancreatic cyst risk-stratification and clinical decision-support platform. It supports clinician review; it is not an autonomous diagnosis or treatment system. No clinical validation or regulatory approval is claimed.

## Architecture and structure

`ml/` holds baseline and experimental model work; `backend/` is the planned FastAPI backend; `frontend/` is the planned React/TypeScript doctor and patient interfaces. `docs/` holds shared contracts and team workflow; `fixtures/` contains synthetic examples only.

## Team ownership

- Jaiganesh: experimental ML, training, radiomics, artifacts and evaluation.
- Aditya: Kyoto 2024 IPMN guideline, trust/concordance semantics and OCR rules.
- Rohith: Cyst-X baseline, backend, infrastructure and integrations.
- Roshan: React/TypeScript portals, CareLoop and food UI.

## Workflow

Use feature branches `feature/jaiganesh-ml`, `feature/aditya-trust-ocr`, `feature/rohith-backend`, and `feature/roshan-frontend`. Meaningful changes go through PRs; see `docs/engineering-integration.md`.

## API contract

Frontend never guesses backend data. Backend never assumes frontend requirements. Both follow `docs/api-contract.md`. Backend schemas are in `backend/app/schemas/`; frontend types are in `frontend/src/types/`.

## Local development and testing

Commands will be defined when project configuration is ready. CI is currently a safe placeholder.

## Security and safety

Never commit secrets, patient information, MRI data, or model weights. Use synthetic fixtures only. See `docs/safety-boundaries.md`.
