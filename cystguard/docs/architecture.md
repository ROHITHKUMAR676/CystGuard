# Architecture

## Boundaries
- ml/: Cyst-X baseline, experiments, radiomics, trust and evaluation.
- backend/: planned FastAPI APIs, schemas, orchestration and integrations.
- frontend/: planned React/TypeScript doctor and patient portals.
- docs/api-contract.md: authoritative frontend/backend contract.

## Planned flow
MRI and clinical inputs will be orchestrated by backend services and presented for clinician review alongside model and guideline outputs. No functioning flow is implemented.

Detailed implementation will be filled progressively.
