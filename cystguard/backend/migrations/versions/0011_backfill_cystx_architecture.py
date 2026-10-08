"""Backfill architecture for assessments made by the known Cyst-X baseline."""

from alembic import op


revision = "0011_backfill_cystx_architecture"
down_revision = "0010_assessment_architecture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE assessments SET architecture = '3D DenseNet-121' "
        "WHERE model_id = 'cystx' AND model_version = 'cystx-baseline-v1' "
        "AND architecture IS NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE assessments SET architecture = NULL "
        "WHERE model_id = 'cystx' AND model_version = 'cystx-baseline-v1' "
        "AND architecture = '3D DenseNet-121'"
    )
