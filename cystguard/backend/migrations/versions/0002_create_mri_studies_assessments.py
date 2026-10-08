"""Create MRI study and assessment tables for the core MRI path."""

from alembic import op
import sqlalchemy as sa

revision = "0002_create_mri_assessments"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mri_studies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=False),
        sa.Column("file_format", sa.String(length=8), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_mri_studies_owner_user_id", "mri_studies", ["owner_user_id"], unique=False)

    op.create_table(
        "assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mri_study_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("risk_class", sa.String(length=64), nullable=True),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("prediction_status", sa.String(length=7), nullable=False),
        sa.Column("input_quality_status", sa.String(length=13), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mri_study_id"], ["mri_studies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessments_mri_study_id", "assessments", ["mri_study_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assessments_mri_study_id", table_name="assessments")
    op.drop_table("assessments")
    op.drop_index("ix_mri_studies_owner_user_id", table_name="mri_studies")
    op.drop_table("mri_studies")
