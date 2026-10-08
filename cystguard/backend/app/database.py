from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


def normalize_database_url(value: str) -> URL:
    """Return a SQLAlchemy URL using the installed synchronous PostgreSQL driver."""
    if value.startswith("postgres://"):
        value = "postgresql://" + value.removeprefix("postgres://")
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = normalize_database_url(get_settings().database_url)
    options = {"pool_pre_ping": True}
    if url.drivername.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
