"""Add patient MRI timeline, structured measurements and surveillance records."""

from alembic import op
import sqlalchemy as sa

revision = "0004_longitudinal_surveillance"
down_revision = "0003_add_document_ocr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mri_studies") as batch_op:
        batch_op.add_column(sa.Column("patient_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("study_date", sa.Date(), nullable=True))
        batch_op.create_foreign_key("fk_mri_studies_patient_user_id", "users", ["patient_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_mri_studies_patient_user_id", "mri_studies", ["patient_user_id"])
    op.create_table("patient_doctor_access",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("patient_user_id", sa.Integer(), nullable=False),
        sa.Column("doctor_user_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("patient_user_id", "doctor_user_id", name="uq_patient_doctor_access"))
    op.create_index("ix_patient_doctor_access_patient_user_id", "patient_doctor_access", ["patient_user_id"])
    op.create_index("ix_patient_doctor_access_doctor_user_id", "patient_doctor_access", ["doctor_user_id"])
    op.create_table("study_measurements",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("study_id", sa.String(36), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("feature", sa.String(64), nullable=False),
        sa.Column("value", sa.Float()), sa.Column("unit", sa.String(32)), sa.Column("finding_status", sa.String(16)),
        sa.Column("measured_at", sa.Date()), sa.Column("source", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False), sa.Column("confidence", sa.Float()),
        sa.Column("verification_status", sa.String(16), nullable=False), sa.Column("comparability", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["mri_studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"))
    op.create_index("ix_study_measurements_study_id", "study_measurements", ["study_id"])
    op.create_index("ix_study_measurements_feature", "study_measurements", ["feature"])
    op.create_table("surveillance_plans",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_user_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("target_follow_up_date", sa.Date(), nullable=False),
        sa.Column("interval", sa.Integer()), sa.Column("interval_unit", sa.String(16)), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("notes", sa.Text()),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)), sa.Column("next_review_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"))
    op.create_index("ix_surveillance_plans_patient_user_id", "surveillance_plans", ["patient_user_id"])
    op.create_table("surveillance_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("notes", sa.Text()), sa.Column("reviewed_by_user_id", sa.Integer()),
        sa.ForeignKeyConstraint(["plan_id"], ["surveillance_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"))
    op.create_index("ix_surveillance_events_plan_id", "surveillance_events", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_surveillance_events_plan_id", table_name="surveillance_events")
    op.drop_table("surveillance_events")
    op.drop_index("ix_surveillance_plans_patient_user_id", table_name="surveillance_plans")
    op.drop_table("surveillance_plans")
    op.drop_index("ix_study_measurements_feature", table_name="study_measurements")
    op.drop_index("ix_study_measurements_study_id", table_name="study_measurements")
    op.drop_table("study_measurements")
    op.drop_index("ix_patient_doctor_access_doctor_user_id", table_name="patient_doctor_access")
    op.drop_index("ix_patient_doctor_access_patient_user_id", table_name="patient_doctor_access")
    op.drop_table("patient_doctor_access")
    op.drop_index("ix_mri_studies_patient_user_id", table_name="mri_studies")
    with op.batch_alter_table("mri_studies") as batch_op:
        batch_op.drop_constraint("fk_mri_studies_patient_user_id", type_="foreignkey")
        batch_op.drop_column("study_date")
        batch_op.drop_column("patient_user_id")
