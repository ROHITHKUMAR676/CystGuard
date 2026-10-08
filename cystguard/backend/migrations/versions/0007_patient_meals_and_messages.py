"""Persist patient meal entries and care-team messages."""

from alembic import op
import sqlalchemy as sa


revision = "0007_patient_meals_messages"
down_revision = "0006_user_profile_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("patient_confirmed", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_entries_patient_id", "meal_entries", ["patient_id"])
    op.create_table(
        "care_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_care_messages_patient_id", "care_messages", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_care_messages_patient_id", table_name="care_messages")
    op.drop_table("care_messages")
    op.drop_index("ix_meal_entries_patient_id", table_name="meal_entries")
    op.drop_table("meal_entries")
