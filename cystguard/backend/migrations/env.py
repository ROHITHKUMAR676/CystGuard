from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.auth.models import PatientDoctorAccess, User  # noqa: F401 - register model metadata.
from app.audit.models import AuditEvent  # noqa: F401 - register model metadata.
from app.config import get_settings
from app.database import Base, normalize_database_url
from app.mri.models import Assessment, MRIStudy  # noqa: F401 - register model metadata.
from app.ocr.models import MedicalReport, MedicationConflict, MedicationRecord, OCRDocument  # noqa: F401
from app.mri.models import StudyMeasurement  # noqa: F401
from app.surveillance.models import SurveillanceEvent, SurveillancePlan  # noqa: F401
from app.workflow.models import CareLoopEvent, CareMessage, ClinicalNote, MealEntry, NutritionObservation, NutritionProfile, ReviewItem, Symptom  # noqa: F401

config = context.config
database_url = normalize_database_url(get_settings().database_url).render_as_string(hide_password=False)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=normalize_database_url(get_settings().database_url).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
