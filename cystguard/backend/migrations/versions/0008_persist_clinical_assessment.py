"""Persist structured clinical, Kyoto, trust, and explanation results."""

from alembic import op
import sqlalchemy as sa


revision = "0008_clinical_assessment"
down_revision = "0007_patient_meals_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("clinical_context", sa.JSON(), nullable=True))
    op.add_column("assessments", sa.Column("guideline_result", sa.JSON(), nullable=True))
    op.add_column("assessments", sa.Column("trust_result", sa.JSON(), nullable=True))
    op.add_column("assessments", sa.Column("explanation_result", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessments", "explanation_result")
    op.drop_column("assessments", "trust_result")
    op.drop_column("assessments", "guideline_result")
    op.drop_column("assessments", "clinical_context")
