"""Add patient symptoms, notes, CareLoop events and clinician review items."""

from alembic import op
import sqlalchemy as sa

revision = "0005_patient_careloop_workflow"
down_revision = "0004_longitudinal_surveillance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("symptoms",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("symptom_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.Integer()), sa.Column("onset_date", sa.Date()), sa.Column("duration", sa.String(64)),
        sa.Column("notes", sa.Text()), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False), sa.Column("review_status", sa.String(16), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer()), sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()), sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"))
    op.create_index("ix_symptoms_patient_id", "symptoms", ["patient_id"])
    op.create_table("clinical_notes",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False), sa.Column("author_role", sa.String(16), nullable=False),
        sa.Column("visibility", sa.String(24), nullable=False), sa.Column("source_context", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="CASCADE"))
    op.create_index("ix_clinical_notes_patient_id", "clinical_notes", ["patient_id"])
    op.create_table("careloop_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer()), sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("source_type", sa.String(48)), sa.Column("source_id", sa.String(36)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("summary", sa.String(255)),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"))
    op.create_index("ix_careloop_events_patient_id", "careloop_events", ["patient_id"])
    op.create_index("ix_careloop_events_occurred_at", "careloop_events", ["occurred_at"])
    op.create_table("review_items",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("item_type", sa.String(48), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_type", sa.String(48)), sa.Column("source_id", sa.String(36)), sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by_user_id", sa.Integer()), sa.Column("resolution_note", sa.Text()),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"))
    op.create_index("ix_review_items_patient_id", "review_items", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_review_items_patient_id", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index("ix_careloop_events_occurred_at", table_name="careloop_events")
    op.drop_index("ix_careloop_events_patient_id", table_name="careloop_events")
    op.drop_table("careloop_events")
    op.drop_index("ix_clinical_notes_patient_id", table_name="clinical_notes")
    op.drop_table("clinical_notes")
    op.drop_index("ix_symptoms_patient_id", table_name="symptoms")
    op.drop_table("symptoms")
