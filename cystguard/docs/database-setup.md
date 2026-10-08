# Backend database setup

The deployed application database is PostgreSQL. Supabase is used as a hosted PostgreSQL provider; the backend uses SQLAlchemy and psycopg 3 directly for relational data. The application does not use Supabase Auth or a Supabase database SDK. Alembic migrations are the schema source of truth.

## Supabase PostgreSQL

1. Create a Supabase project and set a strong database password.
2. In the Supabase Dashboard, open **Connect** and copy the PostgreSQL connection string. Use a direct connection for a persistent FastAPI service and for migrations. Direct connections use port `5432`; Supabase documents them as IPv6 unless the project's IPv4 add-on is enabled.
3. If the runtime network is IPv4-only, use Supabase's shared **session** pooler connection (port `5432`) instead. Copy the complete username and host shown by the dashboard. Do not construct the pooler host yourself. Avoid transaction-mode pooler URLs (port `6543`) for this persistent synchronous service and for Alembic migrations.
4. Copy `.env.example` to `.env`, then set `DATABASE_URL`. Expected SQLAlchemy URL form:

   ```text
   postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
   ```

   Supabase's dashboard may supply `postgresql://` or `postgres://`; the backend selects the installed `psycopg` driver for those schemes. Keep `sslmode=require` for encrypted transport. For server identity verification, configure the Supabase CA certificate and `sslmode=verify-full` according to your deployment environment. Percent-encode reserved characters in the password before placing it in the URL. Never commit `.env` or paste a connection string into source code.
5. Install backend dependencies and run the schema migrations from `backend/`:

   ```sh
   python -m pip install -r requirements.txt
   alembic upgrade head
   ```

   When the application runtime uses a pooled URL, set `DATABASE_URL` to the direct migration URL while running Alembic, then restore the runtime URL.
6. Start FastAPI:

   ```sh
   uvicorn app.main:app --reload
   ```

7. `GET /api/v1/health` is a lightweight liveness check and does not query the database. Use authenticated `GET /api/v1/health/database` to verify connectivity; the response reports only `connected` and never includes connection details.
8. Run tests from `backend/` with `python -m pytest -q`.

## Local SQLite and PostgreSQL validation

When `DATABASE_URL` is unset or blank, the backend retains its SQLite development default. The standard tests use isolated in-memory SQLite and do not need Supabase. `.env.example` shows the PostgreSQL production placeholder; replace it with a valid URL or clear it to select SQLite locally.

For the opt-in PostgreSQL compatibility test, set `TEST_DATABASE_URL` to a **dedicated disposable PostgreSQL database**. The test runs `alembic upgrade head`, validates a connection and required tables/foreign keys, then inserts representative synthetic CystGuard records and rolls back the data transaction. The migration itself is intentionally retained, so do not point this variable at a production database. If `TEST_DATABASE_URL` is absent, this test is skipped.

```sh
TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/test_db?sslmode=require' python -m pytest tests/test_postgres_integration.py -q
```

SQLite remains the fast default test database; PostgreSQL validation is separate and opt-in. Large MRI and document binaries stay in the configured storage backend, outside PostgreSQL; the database stores metadata and storage keys.

For Supabase connection modes, IPv4/IPv6 availability, and SSL configuration, see [Supabase: Connect to your database](https://supabase.com/docs/guides/database/connecting-to-postgres). For Supabase's SQLAlchemy guidance, see [Using SQLAlchemy with Supabase](https://supabase.com/docs/guides/troubleshooting/using-sqlalchemy-with-supabase-FUqebT).
