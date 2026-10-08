from app.ocr.provider import OCRPage, OCRResult, get_ocr_provider
from app.schemas.report import VerificationStatus
from app.auth.models import UserRole
from app.audit.models import AuditEvent
from app.ocr.models import OCRDocument


REPORT_TEXT = """Report type: MRI report
Patient name: Synthetic Patient
Patient ID: SYN-001
Report date: 2025-03-14
Study date: 2025-03-13
Modality: MRI
Body region: pancreas
Findings: Pancreatic cystic lesion measuring 2.8 cm in the head. MPD measures 6 mm. No mural nodule is described.
Impression: Cystic lesion in the pancreatic head.
"""


class StaticProvider:
    def __init__(self, text=REPORT_TEXT, confidence=0.91):
        self.text = text
        self.confidence = confidence

    def extract(self, content, media_type):
        return OCRResult((OCRPage(1, self.text, self.confidence),), "synthetic-test-provider")


def token(client, email):
    return client.post("/api/v1/auth/login", json={"email": email, "password": "strong-test-password"}).json()["access_token"]


def upload_report(client, auth, filename="report.pdf", content=b"%PDF-synthetic"):
    client.app.dependency_overrides[get_ocr_provider] = lambda: StaticProvider()
    headers = {"Authorization": f"Bearer {auth}"} if auth else {}
    return client.post("/api/v1/reports/documents", headers=headers,
                       files={"upload": (filename, content, "application/pdf")})


def test_report_document_extracts_fields_raw_text_and_provenance(client, registered_user, mri_storage_dir):
    auth = token(client, registered_user["email"])
    response = upload_report(client, auth)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["document"]["verification_status"] == "UNVERIFIED"
    assert result["document"]["extraction_status"] == "EXTRACTED"
    assert result["document"]["raw_text"] == REPORT_TEXT
    assert result["document"]["normalized_text"]
    assert result["fields"]["cyst_size_mm"]["value"] == "2.8 cm"
    assert result["fields"]["cyst_size_mm"]["normalized_value"] == "28 mm"
    assert result["fields"]["mpd_mm"]["value"] == "6 mm"
    assert result["fields"]["mpd_mm"]["normalized_value"] == "6 mm"
    field = result["fields"]["cyst_size_mm"]
    assert field["needs_verification"] is True
    assert field["extraction_confidence"] == 0.91
    assert field["provenance"]["source_document_id"] == result["document"]["id"]
    assert field["provenance"]["page"] == 1
    assert field["provenance"]["source_text"]
    assert "storage_key" not in result["document"]
    with client.app.state.test_session_factory() as db:
        stored = db.get(OCRDocument, result["document"]["id"])
        assert stored is not None
        assert (mri_storage_dir / stored.storage_key).is_file()


def test_report_missing_fields_stay_unknown_and_low_confidence_is_exposed(client, registered_user):
    client.app.dependency_overrides[get_ocr_provider] = lambda: StaticProvider("A report with no measurements.", 0.18)
    auth = token(client, registered_user["email"])
    response = client.post("/api/v1/reports/documents", headers={"Authorization": f"Bearer {auth}"},
                           files={"upload": ("short.pdf", b"%PDF-synthetic", "application/pdf")})
    assert response.status_code == 201
    result = response.json()
    assert result["fields"]["mpd_mm"]["status"] == "UNKNOWN"
    assert result["fields"]["mpd_mm"]["value"] is None
    assert result["document"]["extraction_confidence"] == 0.18
    assert result["fields"]["report_type"]["needs_verification"] is True


def test_report_validation_and_auth(client, registered_user):
    auth = token(client, registered_user["email"])
    assert client.post("/api/v1/reports/documents", files={"upload": ("x.pdf", b"%PDF-test", "application/pdf")}).status_code == 401
    headers = {"Authorization": f"Bearer {auth}"}
    assert client.post("/api/v1/reports/documents", headers=headers,
                       files={"upload": ("bad.pdf", b"not-pdf", "application/pdf")}).status_code == 422
    assert client.post("/api/v1/reports/documents", headers=headers,
                       files={"upload": ("bad.exe", b"x", "application/octet-stream")}).status_code == 415


def test_report_verification_and_authorization(client, registered_user):
    auth = token(client, registered_user["email"])
    result = upload_report(client, auth).json()
    report_id = result["id"]
    patient = client.post("/api/v1/auth/register", json={
        "email": "patient-ocr@example.test", "password": "strong-test-password", "role": "PATIENT",
    }).json()
    patient_token = token(client, patient["email"])
    path = f"/api/v1/reports/{report_id}"
    assert client.get(path, headers={"Authorization": f"Bearer {patient_token}"}).status_code == 404
    assert client.post(f"{path}/verify", headers={"Authorization": f"Bearer {patient_token}"}, json={}).status_code == 403
    verified = client.post(f"{path}/verify", headers={"Authorization": f"Bearer {auth}"},
                           json={"fields": {"mpd_mm": 6.0}, "doctor_note": "Checked against source."})
    assert verified.status_code == 200, verified.text
    assert verified.json()["document"]["verification_status"] == VerificationStatus.VERIFIED.value
    assert verified.json()["verified_fields"] == {"mpd_mm": 6.0}
    assert verified.json()["fields"]["mpd_mm"]["value"] == "6 mm"
    assert client.get(f"/api/v1/reports/ocr/{report_id}", headers={"Authorization": f"Bearer {auth}"}).status_code == 200
    with client.app.state.test_session_factory() as db:
        event = db.query(AuditEvent).filter_by(action="REPORT_OCR_VERIFIED").one()
        assert event.actor_user_id == registered_user["id"]
        assert "source_text" not in event.event_metadata


def test_report_extraction_is_not_kyoto_input(client, registered_user):
    auth = token(client, registered_user["email"])
    result = upload_report(client, auth).json()
    assert "kyoto" not in result
    assert result["document"]["verification_status"] == "UNVERIFIED"


def test_patient_report_visible_and_verifiable_only_with_active_doctor_grant(client, registered_user):
    doctor_token = token(client, registered_user["email"])
    patient = client.post("/api/v1/auth/register", json={
        "email": "report-owner@example.test", "password": "strong-test-password", "role": "PATIENT",
    }).json()
    other_doctor = client.post("/api/v1/auth/register", json={
        "email": "other-report-doctor@example.test", "password": "strong-test-password", "role": "DOCTOR",
    }).json()
    patient_token = token(client, patient["email"])
    other_token = token(client, other_doctor["email"])
    report = upload_report(client, patient_token).json()
    patient_id = patient["id"]

    with client.app.state.test_session_factory() as db:
        from app.auth.models import User
        doctor = db.get(User, registered_user["id"])
        access_code = doctor.access_code
    requested = client.post("/api/v1/patients/access-requests", headers={"Authorization": f"Bearer {patient_token}"},
                            json={"doctor_access_code": access_code})
    assert requested.status_code == 201, requested.text
    assert client.post(f"/api/v1/patients/{patient_id}/doctors/{registered_user['id']}/approve-access",
                       headers={"Authorization": f"Bearer {doctor_token}"}).status_code == 200

    patient_reports = client.get("/api/v1/reports/patients/" + str(patient_id),
                                 headers={"Authorization": f"Bearer {doctor_token}"})
    assert patient_reports.status_code == 200, patient_reports.text
    assert [row["id"] for row in patient_reports.json()] == [report["id"]]
    assert client.get(f"/api/v1/reports/{report['id']}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
    verified = client.post(f"/api/v1/reports/{report['id']}/verify", headers={"Authorization": f"Bearer {doctor_token}"},
                           json={"fields": {"mpd_mm": 6.0}, "doctor_note": "Reviewed source report."})
    assert verified.status_code == 200, verified.text

    assert client.post(f"/api/v1/patients/{patient_id}/doctors/{registered_user['id']}/revoke",
                       headers={"Authorization": f"Bearer {patient_token}"}).status_code == 200
    assert client.get("/api/v1/reports/patients/" + str(patient_id),
                      headers={"Authorization": f"Bearer {doctor_token}"}).status_code == 404
