"""Add user profile identity and doctor-reviewable access requests."""

import secrets

from alembic import op
import sqlalchemy as sa


revision = "0006_user_profile_access"
down_revision = "0005_patient_careloop_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("access_code", sa.String(length=24), nullable=True))
    op.create_index("ix_users_access_code", "users", ["access_code"], unique=True)

    bind = op.get_bind()
    doctors = bind.execute(sa.text("SELECT id FROM users WHERE role = 'DOCTOR'")).fetchall()
    for (doctor_id,) in doctors:
        bind.execute(sa.text("UPDATE users SET access_code = :code WHERE id = :id"),
                     {"id": doctor_id, "code": f"CG-{secrets.token_hex(3).upper()}"})

    # Old direct patient grants remain active; new registrations create PENDING rows.
    op.create_index("ix_patient_doctor_access_status", "patient_doctor_access", ["status"])


def downgrade() -> None:
    op.drop_index("ix_patient_doctor_access_status", table_name="patient_doctor_access")
    op.drop_index("ix_users_access_code", table_name="users")
    op.drop_column("users", "access_code")
    op.drop_column("users", "display_name")
