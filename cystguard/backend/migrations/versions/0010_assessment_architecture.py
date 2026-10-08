"""Record the model architecture used for MRI assessment."""

from alembic import op
import sqlalchemy as sa


revision = "0010_assessment_architecture"
down_revision = "0009_meal_nutrition_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("architecture", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("assessments", "architecture")
