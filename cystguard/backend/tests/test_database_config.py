from app.database import normalize_database_url


def test_postgres_urls_select_psycopg_and_preserve_ssl_settings():
    url = normalize_database_url("postgresql://postgres:p%40ss@db.example.test:5432/cystguard?sslmode=require")
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss"
    assert url.query["sslmode"] == "require"


def test_supabase_legacy_scheme_and_sqlite_remain_supported():
    assert normalize_database_url("postgres://user:pass@pooler.example.test:5432/postgres").drivername == "postgresql+psycopg"
    assert normalize_database_url("sqlite:///./cystguard.db").drivername == "sqlite"
