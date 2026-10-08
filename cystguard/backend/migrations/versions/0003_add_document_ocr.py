"""Persist OCR documents, extracted report/medication data, conflicts, and audits."""

from alembic import op
import sqlalchemy as sa

revision = "0003_add_document_ocr"
down_revision = "0002_create_mri_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ocr_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(10), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("extraction_status", sa.String(9), nullable=False),
        sa.Column("verification_status", sa.String(10), nullable=False),
        sa.Column("extraction_method", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ocr_documents_owner_user_id", "ocr_documents", ["owner_user_id"])

    op.create_table(
        "medical_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False, unique=True),
        sa.Column("extracted_fields", sa.JSON(), nullable=False),
        sa.Column("verified_fields", sa.JSON(), nullable=True),
        sa.Column("doctor_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["ocr_documents.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "medication_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("extracted_fields", sa.JSON(), nullable=False),
        sa.Column("verified_fields", sa.JSON(), nullable=True),
        sa.Column("verification_status", sa.String(10), nullable=False),
        sa.Column("medication_status", sa.String(12), nullable=False),
        sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("doctor_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["ocr_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_medication_records_document_id", "medication_records", ["document_id"])
    op.create_index("ix_medication_records_owner_user_id", "medication_records", ["owner_user_id"])
    op.create_index("ix_medication_records_patient_id", "medication_records", ["patient_id"])

    op.create_table(
        "medication_conflicts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("left_record_id", sa.String(36), nullable=False),
        sa.Column("right_record_id", sa.String(36), nullable=False),
        sa.Column("conflicting_fields", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("resolution_record_id", sa.String(36), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["left_record_id"], ["medication_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["right_record_id"], ["medication_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolution_record_id"], ["medication_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_medication_conflict_owner_status", "medication_conflicts", ["owner_user_id", "status"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_resource_id", "audit_events", ["resource_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_resource_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_medication_conflict_owner_status", table_name="medication_conflicts")
    op.drop_table("medication_conflicts")
    op.drop_index("ix_medication_records_patient_id", table_name="medication_records")
    op.drop_index("ix_medication_records_owner_user_id", table_name="medication_records")
    op.drop_index("ix_medication_records_document_id", table_name="medication_records")
    op.drop_table("medication_records")
    op.drop_table("medical_reports")
    op.drop_index("ix_ocr_documents_owner_user_id", table_name="ocr_documents")
    op.drop_table("ocr_documents")
