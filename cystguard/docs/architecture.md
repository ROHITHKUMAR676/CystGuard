# Architecture

## Boundaries

- `ml/`: Cyst-X baseline and isolated model work.
- `backend/`: synchronous FastAPI APIs, SQLAlchemy persistence, domain services, and integrations.
- `frontend/`: React/TypeScript client; it calls the backend contract and does not connect to the database.
- `docs/api-contract.md`: authoritative frontend/backend contract.

## Database and storage

PostgreSQL is the deployment database. Supabase supplies hosted PostgreSQL; the backend connects through SQLAlchemy and the psycopg 3 driver, without Supabase client SDKs for relational CRUD. `DATABASE_URL` configures both the application engine and Alembic. Alembic migrations are the schema source of truth. SQLite remains the default when `DATABASE_URL` is unset for lightweight local and automated tests; PostgreSQL integration validation is opt-in through `TEST_DATABASE_URL`.

MRI and document binaries remain in the storage abstraction (local filesystem for development, replaceable by object storage); PostgreSQL stores metadata, opaque storage keys, structured extracted facts, and audit events.

See [database setup](database-setup.md) for Supabase connection and migration instructions.

## Clinical workflow

MRI and explicitly sourced clinical records are persisted by the backend and made available for clinician review. Cyst-X, Kyoto, and trust outputs remain distinct evidence streams. CareLoop is a workflow timeline, not a recommendation engine. No autonomous diagnosis or treatment decision is made.
