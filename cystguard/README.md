# CystGuard

AI-assisted pancreatic cyst risk-stratification and clinical decision-support platform. It supports clinician review; it is not an autonomous diagnosis or treatment system. No clinical validation or regulatory approval is claimed.

## Architecture and structure

`ml/` holds baseline and experimental model work; `backend/` contains the FastAPI API and persistence layer; `frontend/` contains the browser application. `docs/` holds shared contracts and team workflow; `fixtures/` contains synthetic examples only.

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

Backend installation, SQLite defaults, Supabase PostgreSQL configuration, migrations, and tests are documented in [docs/database-setup.md](docs/database-setup.md). Alembic is the schema source of truth. PostgreSQL integration tests run only when `TEST_DATABASE_URL` points to a disposable database.

Run the application locally in two terminals after setting `SECRET_KEY` and `DATABASE_URL` in the root `.env` (or leave `DATABASE_URL` blank to use SQLite):

```sh
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

```sh
cd frontend
npm run dev
```

The frontend calls `http://127.0.0.1:8000/api/v1` by default. Set `window.CYSTGUARD_API_URL` before loading `frontend/index.html` to use another API origin. Patient tabs work for the authenticated patient before a clinician connection is approved; approval gates clinician access to that patient's records.

## Security and safety

Never commit secrets, patient information, MRI data, or model weights. Use synthetic fixtures only. See `docs/safety-boundaries.md`.
