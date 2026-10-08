from datetime import date

from sqlalchemy import select

from app.audit.models import AuditEvent


def _create_user(client, email, role):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "strong-test-password", "role": role,
    })
    assert response.status_code == 201
    user = response.json()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "strong-test-password"})
    assert login.status_code == 200
    return user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_care_profile_for_new_patient_without_optional_care_data(client):
    patient, patient_headers = _create_user(client, "new-patient@example.test", "PATIENT")

    response = client.get(f"/api/v1/patients/{patient['id']}/care-profile", headers=patient_headers)

    assert response.status_code == 200
    profile = response.json()
    assert profile["patient_id"] == patient["id"]
    assert profile["active_doctors"] == []
    assert profile["latest_mri"] is None
    assert profile["latest_assessment"] is None
    assert profile["longitudinal_summary"] == {
        "study_count": 0,
        "previous_study_id": None,
        "latest_comparison": None,
        "status": "UNKNOWN",
    }
    assert profile["surveillance"] == {
        "plans": [], "events": [], "status": "UNKNOWN",
    }
    assert profile["medications"] == []
    assert profile["symptoms"] == []
    assert profile["meals"] == {"status": "UNKNOWN", "entries": []}
    assert profile["recent_clinician_notes"] == {"status": "UNKNOWN", "items": []}
    assert profile["review_queue"] == {"status": "UNKNOWN", "has_open_items": False}


def test_patient_workflow_authorization_symptoms_notes_reviews_and_audit(client):
    patient, patient_headers = _create_user(client, "p7-patient@example.test", "PATIENT")
    doctor, doctor_headers = _create_user(client, "p7-doctor@example.test", "DOCTOR")
    patient_id, doctor_id = patient["id"], doctor["id"]

    own_profile = client.get(f"/api/v1/patients/{patient_id}/care-profile", headers=patient_headers)
    assert own_profile.status_code == 200
    assert own_profile.json()["meals"]["status"] == "UNKNOWN"
    assert own_profile.json()["latest_assessment"] is None
    assert client.get(f"/api/v1/patients/{patient_id}/care-profile", headers=doctor_headers).status_code == 404

    symptom_response = client.post(f"/api/v1/patients/{patient_id}/symptoms", headers=patient_headers, json={
        "symptom_type": "ABDOMINAL_DISCOMFORT", "severity": 3, "onset_date": date.today().isoformat(),
        "status": "ACTIVE", "notes": "Patient report",
    })
    assert symptom_response.status_code == 201
    symptom = symptom_response.json()
    assert symptom["review_status"] == "PENDING_REVIEW"
    assert "diagnosis" not in symptom
    assert client.get(f"/api/v1/patients/{patient_id}/symptoms", headers=doctor_headers).status_code == 404

    grant = client.post(f"/api/v1/patients/{patient_id}/doctors/{doctor_id}/access", headers=patient_headers)
    assert grant.status_code == 201
    assert grant.json()["status"] == "PENDING"
    assert client.get(f"/api/v1/patients/{patient_id}/symptoms", headers=doctor_headers).status_code == 404
    approved = client.post(f"/api/v1/patients/{patient_id}/doctors/{doctor_id}/approve-access", headers=doctor_headers)
    assert approved.status_code == 200
    doctor_symptoms = client.get(f"/api/v1/patients/{patient_id}/symptoms", headers=doctor_headers)
    assert doctor_symptoms.status_code == 200 and doctor_symptoms.json()[0]["id"] == symptom["id"]

    reviewed = client.patch(f"/api/v1/patients/{patient_id}/symptoms/{symptom['id']}", headers=doctor_headers,
                            json={"review_note": "Reviewed with patient"})
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewed_by_user_id"] == doctor_id
    note = client.post(f"/api/v1/patients/{patient_id}/notes", headers=doctor_headers, json={
        "body": "Clinician workflow note", "visibility": "CLINICIAN_ONLY", "source_context": "VISIT",
    })
    assert note.status_code == 201 and note.json()["author_user_id"] == doctor_id
    patient_notes = client.get(f"/api/v1/patients/{patient_id}/notes", headers=patient_headers)
    assert patient_notes.status_code == 200 and patient_notes.json() == []
    assert client.get(f"/api/v1/patients/{patient_id}/notes", headers=doctor_headers).json()[0]["body"] == "Clinician workflow note"

    reviews = client.get(f"/api/v1/patients/{patient_id}/reviews", headers=doctor_headers)
    assert reviews.status_code == 200 and reviews.json()[0]["source_id"] == symptom["id"]
    review_id = reviews.json()[0]["id"]
    resolved = client.post(f"/api/v1/patients/{patient_id}/reviews/{review_id}/resolve", headers=doctor_headers,
                           json={"resolution_note": "Reviewed", "status": "RESOLVED"})
    assert resolved.status_code == 200
    assert resolved.json()["resolved_by_user_id"] == doctor_id
    assert resolved.json()["resolution_note"] == "Reviewed"
    assert client.get(f"/api/v1/patients/{patient_id}/careloop", headers=patient_headers).status_code == 200

    with client.app.state.test_session_factory() as db:
        actions = set(db.scalars(select(AuditEvent.action)).all())
    assert {"PATIENT_ACCESS_REQUESTED", "SYMPTOM_CREATED", "CLINICAL_NOTE_CREATED", "REVIEW_ITEM_CREATED", "REVIEW_ITEM_RESOLVED"} <= actions


def test_workflow_doctor_access_revocation_and_visit_preparation(client):
    patient, patient_headers = _create_user(client, "p7-patient2@example.test", "PATIENT")
    doctor, doctor_headers = _create_user(client, "p7-doctor2@example.test", "DOCTOR")
    patient_id, doctor_id = patient["id"], doctor["id"]
    client.post(f"/api/v1/patients/{patient_id}/doctors/{doctor_id}/access", headers=patient_headers)
    client.post(f"/api/v1/patients/{patient_id}/doctors/{doctor_id}/approve-access", headers=doctor_headers)
    summary = client.get(f"/api/v1/patients/{patient_id}/visit-preparation", headers=doctor_headers)
    assert summary.status_code == 200
    data = summary.json()
    assert data["kyoto_assessment"]["status"] == "UNKNOWN"
    assert data["trust_concordance"]["status"] == "UNKNOWN"
    assert data["diagnosis"] is None
    assert data["treatment_recommendations"] == []
    revoked = client.post(f"/api/v1/patients/{patient_id}/doctors/{doctor_id}/revoke", headers=patient_headers)
    assert revoked.status_code == 200
    assert client.get(f"/api/v1/patients/{patient_id}/visit-preparation", headers=doctor_headers).status_code == 404
