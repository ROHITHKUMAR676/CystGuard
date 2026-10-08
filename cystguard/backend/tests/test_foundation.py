from app.config import Settings


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authenticated_database_health_endpoint(client, registered_user):
    token = client.post("/api/v1/auth/login", json={
        "email": registered_user["email"], "password": "strong-test-password",
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/health/database").status_code == 401
    response = client.get("/api/v1/health/database", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"database": "connected"}
    assert "url" not in response.text.lower()


def test_settings_load_configuration():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://local:local@localhost/cystguard",
        secret_key="unit-test-key",
        access_token_expire_minutes=45,
        cors_origins="http://localhost:5173, http://127.0.0.1:5173",
        storage_root="/tmp/cystguard-test-storage",
    )
    assert settings.database_url.startswith("postgresql+")
    assert settings.access_token_expire_minutes == 45
    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert str(settings.storage_root).endswith("cystguard-test-storage")


def test_password_hashing():
    from app.auth.security import hash_password, verify_password

    encoded = hash_password("strong-test-password")
    assert encoded != "strong-test-password"
    assert verify_password("strong-test-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_authentication_success(client, registered_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "strong-test-password"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_authentication_failure(client, registered_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "incorrect-password"},
    )
    assert response.status_code == 401


def test_protected_endpoint_rejects_unauthenticated_request(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_access_token_authenticates_current_user(client, registered_user):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "strong-test-password"},
    ).json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == registered_user["email"]
    assert response.json()["role"] == "DOCTOR"
