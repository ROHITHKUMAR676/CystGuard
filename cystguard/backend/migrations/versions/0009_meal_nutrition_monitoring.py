"""Persist FoodCNN meal estimates, patient confirmation, and nutrition monitoring."""

from alembic import op
import sqlalchemy as sa


revision = "0009_meal_nutrition_monitoring"
down_revision = "0008_clinical_assessment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meal_entries", sa.Column("analysis_status", sa.String(length=24), nullable=False,
        server_default="DESCRIPTION_ONLY"))

    for name, type_ in (
        ("food_image_key", sa.String(length=512)),
        ("food_image_content_type", sa.String(length=64)),
        ("food_items", sa.JSON()),
        ("food_context_tags", sa.JSON()),
        ("nutrition_context_flags", sa.JSON()),
        ("raw_provider_output", sa.JSON()),
        ("nutrition_estimate", sa.JSON()),
        ("patient_corrections", sa.JSON()),
        ("final_nutrition", sa.JSON()),
        ("estimated_portion_grams", sa.Float()),
        ("recognition_confidence", sa.Float()),
        ("food_provider", sa.String(length=64)),
        ("food_provider_version", sa.String(length=128)),
        ("food_model_version", sa.String(length=128)),
        ("nutrition_source", sa.String(length=128)),
        ("nutrition_source_version", sa.String(length=128)),
        ("nutrition_estimation_method", sa.String(length=128)),
    ):
        op.add_column("meal_entries", sa.Column(name, type_, nullable=True))

    op.create_table(
        "nutrition_profiles",
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("target_daily_kcal", sa.Float(), nullable=True),
        sa.Column("target_daily_protein_g", sa.Float(), nullable=True),
        sa.Column("documented_pei_pert", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("documented_diabetes", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("patient_id"),
    )

    op.create_table(
        "nutrition_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("appetite", sa.String(length=16), nullable=False),
        sa.Column("reported_symptoms", sa.JSON(), nullable=False),
        sa.Column("intake_interfered", sa.Boolean(), nullable=False),
        sa.Column("intake_day_complete", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nutrition_observations_patient_id", "nutrition_observations", ["patient_id"])
    op.create_index("ix_nutrition_observations_recorded_at", "nutrition_observations", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_nutrition_observations_recorded_at", table_name="nutrition_observations")
    op.drop_index("ix_nutrition_observations_patient_id", table_name="nutrition_observations")
    op.drop_table("nutrition_observations")
    op.drop_table("nutrition_profiles")
    for name in (
        "nutrition_estimation_method", "nutrition_source_version", "nutrition_source",
        "food_model_version", "food_provider_version", "food_provider", "recognition_confidence",
        "estimated_portion_grams", "final_nutrition", "patient_corrections", "nutrition_estimate",
        "raw_provider_output", "nutrition_context_flags", "food_context_tags", "food_items", "food_image_content_type", "food_image_key", "analysis_status",
    ):
        op.drop_column("meal_entries", name)
