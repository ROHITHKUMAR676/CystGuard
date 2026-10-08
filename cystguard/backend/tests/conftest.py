import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import models  # Ensure model metadata is registered before create_all.
from app.audit import models as audit_models  # noqa: F401
from app.config import get_settings
from app.database import Base, get_db
from app.mri import models as mri_models  # Ensure MRI metadata is registered before create_all.
from app.ocr import models as ocr_models  # noqa: F401
from app.surveillance import models as surveillance_models  # noqa: F401
from app.workflow import models as workflow_models  # noqa: F401
from app.main import create_app
from app.storage.service import LocalStorage, get_storage


@pytest.fixture
def mri_storage_dir(tmp_path):
    return tmp_path / "mri-storage"


@pytest.fixture
def client(monkeypatch, tmp_path, mri_storage_dir):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    settings = get_settings().model_copy(update={"secret_key": "test-secret-key-that-is-not-used-outside-tests"})
    monkeypatch.setattr("app.auth.security.get_settings", lambda: settings)
    application = create_app()
    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_storage] = lambda: LocalStorage(mri_storage_dir)
    application.state.test_session_factory = TestSession
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def registered_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "doctor@example.test", "password": "strong-test-password", "role": "DOCTOR"},
    )
    assert response.status_code == 201
    return response.json()
