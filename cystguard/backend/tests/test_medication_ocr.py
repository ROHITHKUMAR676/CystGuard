import json

from app.audit.models import AuditEvent
from app.ocr.provider import OCRPage, OCRResult, get_ocr_provider
from app.ocr.models import MedicationRecord


class StaticMedicationProvider:
    def __init__(self, text, confidence=0.84):
        self.text = text
        self.confidence = confidence

    def extract(self, content, media_type):
        return OCRResult((OCRPage(1, self.text, self.confidence),), "synthetic-test-provider")


def register(client, email, role="PATIENT"):
    user = client.post("/api/v1/auth/register", json={
        "email": email, "password": "strong-test-password", "role": role,
    }).json()
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "strong-test-password"}).json()["access_token"]
    return user, token


def upload_meds(client, auth, text, filename="meds.png", content=b"\x89PNG\r\n\x1a\nsynthetic"):
    client.app.dependency_overrides[get_ocr_provider] = lambda: StaticMedicationProvider(text)
    return client.post("/api/v1/medications/documents", headers={"Authorization": f"Bearer {auth}"},
                       files={"upload": (filename, content, "image/png")})


def test_medication_field_extraction_and_normalization(client):
    patient, auth = register(client, "meds@example.test")
    response = upload_meds(client, auth, "Medication: Metformin 0.5 g, take 1 tablet twice a day by mouth")
    assert response.status_code == 201, response.text
    payload = response.json()
    medication = payload["medications"][0]
    assert medication["extracted_fields"]["name"] == "Metformin"
    assert medication["extracted_fields"]["strength"] == "0.5 g"
    assert medication["extracted_fields"]["normalized_strength"] == "500 mg"
    assert medication["extracted_fields"]["dose"] == "1 tablet"
    assert medication["extracted_fields"]["normalized_frequency"] == "twice daily"
    assert medication["extracted_fields"]["route"] == "by mouth"
    assert medication["extracted_fields"]["normalized_route"] == "oral"
    assert medication["extraction_confidence"] == 0.84
    assert medication["verification_status"] == "UNVERIFIED"
    assert medication["medication_status"] == "UNKNOWN"
    assert payload["document"]["raw_text"].endswith("by mouth")
    assert medication["extracted_fields"]["source_document_id"] == payload["document"]["id"]


def test_missing_medication_values_remain_null_and_ocr_job_readable(client):
    _, auth = register(client, "minimal-meds@example.test")
    uploaded = upload_meds(client, auth, "Medication: Amoxicillin")
    assert uploaded.status_code == 201
    payload = uploaded.json()
    candidate = payload["medications"][0]["extracted_fields"]
    assert candidate["strength"] is None
    assert candidate["dose"] is None
    assert candidate["frequency"] is None
    assert candidate["route"] is None
    fetched = client.get(f"/api/v1/medications/ocr/{payload['document']['id']}", headers={"Authorization": f"Bearer {auth}"})
    assert fetched.status_code == 200
    assert fetched.json()["document"]["raw_text"] == "Medication: Amoxicillin"


def test_invalid_document_and_unauthenticated_request(client):
    _, auth = register(client, "invalid-meds@example.test")
    assert client.post("/api/v1/medications/documents", files={"upload": ("x.png", b"bad", "image/png")}).status_code == 401
    bad = client.post("/api/v1/medications/documents", headers={"Authorization": f"Bearer {auth}"},
                      files={"upload": ("bad.png", b"not-image", "image/png")})
    assert bad.status_code == 422


def test_low_extraction_confidence_and_no_pill_appearance_identification(client):
    _, auth = register(client, "low-confidence@example.test")
    provider = StaticMedicationProvider("Medication: Aspirin 81 mg daily", confidence=0.12)
    client.app.dependency_overrides[get_ocr_provider] = lambda: provider
    low = client.post("/api/v1/medications/documents", headers={"Authorization": f"Bearer {auth}"},
                      files={"upload": ("low.png", b"\x89PNG\r\n\x1a\nsynthetic", "image/png")})
    assert low.status_code == 201
    assert low.json()["medications"][0]["extraction_confidence"] == 0.12

    client.app.dependency_overrides[get_ocr_provider] = lambda: StaticMedicationProvider("")
    blank = client.post("/api/v1/medications/documents", headers={"Authorization": f"Bearer {auth}"},
                        files={"upload": ("pill-photo.png", b"\x89PNG\r\n\x1a\nsynthetic", "image/png")})
    assert blank.status_code == 201
    assert blank.json()["medications"] == []
    body = json.dumps(blank.json()).lower()
    assert "diagnosis" not in body and "prescription" not in body


def test_medication_document_owner_is_enforced(client):
    _, owner_token = register(client, "med-owner@example.test")
    result = upload_meds(client, owner_token, "Medication: Amlodipine 5 mg daily").json()
    _, other_token = register(client, "med-other@example.test")
    response = client.get(f"/api/v1/medications/ocr/{result['document']['id']}",
                          headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 404


def test_conflicting_documents_are_preserved_and_reviewed_without_changing_status(client):
    patient, auth = register(client, "conflict-meds@example.test")
    first = upload_meds(client, auth, "Medication: Metformin 500 mg take 1 tablet once daily").json()
    second = upload_meds(client, auth, "Medication: Metformin 500 mg take 1 tablet twice daily").json()
    assert first["medications"][0]["id"] != second["medications"][0]["id"]
    second_row = second["medications"][0]
    assert second_row["conflicts"]
    conflict = second_row["conflicts"][0]
    assert conflict["status"] == "CONFLICT_REQUIRES_REVIEW"
    assert "normalized_frequency" in conflict["conflicting_fields"]
    before_status = second_row["medication_status"]
    response = client.post(
        f"/api/v1/patients/{patient['id']}/medications/{second_row['id']}/review-conflict",
        headers={"Authorization": f"Bearer {auth}"},
        json={"review_note": "Patient confirmed which source is current; check with prescriber.",
              "resolution_record_id": second_row["id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REVIEWED"
    assert response.json()["review_note"].startswith("Patient confirmed")
    assert response.json()["resolution_record_id"] == second_row["id"]
    listing = client.get(f"/api/v1/patients/{patient['id']}/medications", headers={"Authorization": f"Bearer {auth}"})
    assert listing.status_code == 200 and len(listing.json()) == 2
    assert {x["medication_status"] for x in listing.json()} == {before_status}


def test_patient_ownership_doctor_verification_and_audit(client):
    patient, patient_token = register(client, "owner-meds@example.test")
    uploaded = upload_meds(client, patient_token, "Medication: Metformin 500 mg once daily").json()
    record_id = uploaded["medications"][0]["id"]
    forbidden = client.get(f"/api/v1/patients/{patient['id']}/medications", headers={"Authorization": f"Bearer {register(client, 'other-patient@example.test')[1]}"})
    assert forbidden.status_code == 403
    doctor, doctor_token = register(client, "med-doctor@example.test", "DOCTOR")
    patient_verify = client.post(f"/api/v1/medications/{record_id}/verify", headers={"Authorization": f"Bearer {patient_token}"}, json={})
    assert patient_verify.status_code == 403
    assert client.post(f"/api/v1/medications/{record_id}/verify", headers={"Authorization": f"Bearer {doctor_token}"}, json={}).status_code == 404

    access_request = client.post(
        "/api/v1/patients/access-requests",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"doctor_access_code": doctor["doctor_access_code"]},
    )
    assert access_request.status_code == 201
    approved = client.post(
        f"/api/v1/patients/{patient['id']}/doctors/{doctor['id']}/approve-access",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert approved.status_code == 200
    shared_records = client.get(
        f"/api/v1/patients/{patient['id']}/medications",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert shared_records.status_code == 200
    assert any(row["id"] == record_id for row in shared_records.json())
    verified_patient_record = client.post(
        f"/api/v1/medications/{record_id}/verify",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"fields": {"frequency": "once daily"}, "medication_status": "ACTIVE"},
    )
    assert verified_patient_record.status_code == 200

    # Doctors can verify patient records only after the patient approves access.
    doctor_upload = upload_meds(client, doctor_token, "Medication: Metformin 500 mg once daily").json()
    doctor_record = doctor_upload["medications"][0]
    verified = client.post(f"/api/v1/medications/{doctor_record['id']}/verify", headers={"Authorization": f"Bearer {doctor_token}"},
                           json={"fields": {"frequency": "twice daily"}, "medication_status": "ACTIVE", "doctor_note": "Checked source."})
    assert verified.status_code == 200, verified.text
    assert verified.json()["verification_status"] == "VERIFIED"
    assert verified.json()["medication_status"] == "ACTIVE"
    assert verified.json()["extracted_fields"]["frequency"] == "once daily"
    assert verified.json()["verified_fields"]["frequency"] == "twice daily"
    with client.app.state.test_session_factory() as db:
            events = db.query(AuditEvent).filter_by(action="MEDICATION_OCR_VERIFIED", actor_user_id=doctor["id"]).all()
            assert len(events) == 2
            rows = db.query(MedicationRecord).filter_by(owner_user_id=patient["id"]).all()
            assert rows[0].medication_status.value == "ACTIVE"


def test_no_automatic_discontinuation_on_new_document(client):
    _, auth = register(client, "not-discontinued@example.test")
    first = upload_meds(client, auth, "Medication: Atorvastatin 10 mg once daily").json()
    second = upload_meds(client, auth, "Medication: Vitamin D 1000 IU once daily").json()
    for payload in (first, second):
        assert payload["medications"][0]["medication_status"] == "UNKNOWN"
