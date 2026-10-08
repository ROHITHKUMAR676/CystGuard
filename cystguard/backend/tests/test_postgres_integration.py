"""Opt-in compatibility test for a disposable PostgreSQL database."""

import os
from pathlib import Path
import subprocess
import sys
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import PatientDoctorAccess, User, UserRole
from app.audit.models import AuditEvent
from app.database import normalize_database_url
from app.mri.models import Assessment, InputQualityStatus, MRIFileFormat, MRIStudy, MRIStudyStatus, PredictionStatus
from app.ocr.models import MedicationLifecycleStatus, MedicationRecord, OCRDocument, OCRDocumentType, OCRExtractionStatus, OCRVerificationStatus
from app.surveillance.models import SurveillancePlan
from app.workflow.models import CareLoopEvent, ClinicalNote, ReviewItem, Symptom


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


def test_postgresql_migrations_and_representative_workflow_roundtrip():
    backend_dir = Path(__file__).resolve().parents[1]
    child_env = os.environ.copy()
    child_env["DATABASE_URL"] = TEST_DATABASE_URL
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert migration.returncode == 0, "PostgreSQL migration failed; connection details are intentionally redacted"

    engine = create_engine(normalize_database_url(TEST_DATABASE_URL), pool_pre_ping=True)
    email = f"pg-integration-{uuid4()}@example.test"
    patient_email = f"pg-patient-{uuid4()}@example.test"
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
        tables = set(inspect(engine).get_table_names())
        assert {"users", "patient_doctor_access", "mri_studies", "assessments", "surveillance_plans",
                "ocr_documents", "medication_records", "symptoms", "clinical_notes", "careloop_events",
                "review_items", "audit_events"} <= tables
        assert any(fk["referred_table"] == "users" for fk in inspect(engine).get_foreign_keys("patient_doctor_access"))

        connection = engine.connect()
        outer = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            doctor = User(email=email, hashed_password="synthetic-test-hash", role=UserRole.DOCTOR)
            patient = User(email=patient_email, hashed_password="synthetic-test-hash", role=UserRole.PATIENT)
            session.add_all([doctor, patient])
            session.flush()
            grant = PatientDoctorAccess(patient_user_id=patient.id, doctor_user_id=doctor.id, status="ACTIVE")
            study = MRIStudy(owner_user_id=doctor.id, patient_user_id=patient.id, original_filename="synthetic.nii",
                             storage_key=f"test/{uuid4()}", modality="T1", file_format=MRIFileFormat.NIFTI,
                             status=MRIStudyStatus.UPLOADED)
            session.add_all([grant, study])
            session.flush()
            assessment = Assessment(mri_study_id=study.id, model_id="synthetic-test", model_version="test-v1",
                risk_class="NO_LOW_RISK", raw_score=0.2, threshold=0.5, prediction_status=PredictionStatus.SUCCESS,
                input_quality_status=InputQualityStatus.ACCEPTABLE, fallback_used=False)
            plan = SurveillancePlan(patient_user_id=patient.id, created_by_user_id=doctor.id,
                target_follow_up_date=date.today(), reason="Synthetic integration record")
            document = OCRDocument(owner_user_id=patient.id, document_type=OCRDocumentType.MEDICATION,
                original_filename="synthetic.pdf", content_type="application/pdf", storage_key=f"test/{uuid4()}",
                extraction_status=OCRExtractionStatus.EXTRACTED, verification_status=OCRVerificationStatus.UNVERIFIED,
                extraction_method="synthetic", page_count=1, raw_text="synthetic", normalized_text="synthetic")
            session.add_all([assessment, plan, document])
            session.flush()
            medication = MedicationRecord(document_id=document.id, owner_user_id=patient.id, patient_id=patient.id,
                extracted_fields={"name": "synthetic"}, verified_fields=None,
                verification_status=OCRVerificationStatus.UNVERIFIED, medication_status=MedicationLifecycleStatus.UNKNOWN)
            symptom = Symptom(patient_id=patient.id, created_by_user_id=patient.id, symptom_type="SYNTHETIC",
                              status="UNKNOWN", source="PATIENT_REPORTED")
            note = ClinicalNote(patient_id=patient.id, author_user_id=doctor.id, author_role="DOCTOR",
                                visibility="CLINICIAN_ONLY", source_context="TEST", body="Synthetic note")
            event = CareLoopEvent(patient_id=patient.id, actor_user_id=doctor.id, event_type="TEST_EVENT")
            review = ReviewItem(patient_id=patient.id, created_by_user_id=doctor.id, item_type="TEST_REVIEW")
            audit = AuditEvent(actor_user_id=doctor.id, action="TEST", resource_type="TEST", resource_id=str(uuid4()), event_metadata={})
            session.add_all([medication, symptom, note, event, review, audit])
            session.flush()
            assert session.scalar(select(Assessment).where(Assessment.mri_study_id == study.id)) is not None
            assert session.scalar(select(MedicationRecord).where(MedicationRecord.document_id == document.id)) is not None
            assert session.scalar(select(Symptom).where(Symptom.patient_id == patient.id)) is not None

            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    session.add(User(email=email, hashed_password="duplicate", role=UserRole.DOCTOR))
                    session.flush()
            session.rollback()
        finally:
            session.close()
            outer.rollback()
            connection.close()
        with engine.connect() as connection:
            assert connection.execute(select(User.id).where(User.email == email)).first() is None
    finally:
        engine.dispose()
