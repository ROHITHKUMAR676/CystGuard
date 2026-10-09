import gzip
from datetime import date
import logging
from pathlib import Path
import shutil
import tempfile

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import require_patient_access
from app.auth.models import User, UserRole
from app.config import Settings, get_settings
from app.mri.models import (
    Assessment,
    InputQualityStatus,
    MRIFileFormat,
    MRIStudy,
    MRIStudyStatus,
    PredictionStatus,
)
from app.ml.ml_service import MLService, MLPrediction, ModelConfigurationError, ModelInferenceError
from app.storage.service import StorageBackend, StoredObject

_NIFTI1_MAGIC = b"n+1\x00"
_NIFTI2_MAGIC = b"n+2\x00\r\n\x1a\n"
logger = logging.getLogger(__name__)


def validate_nifti_upload(upload: UploadFile, max_size_bytes: int) -> tuple[str, MRIFileFormat]:
    filename = (upload.filename or "").replace("\\", "/").split("/")[-1]
    if not filename or "\x00" in filename or len(filename) > 255:
        raise HTTPException(status_code=400, detail="A valid MRI filename is required.")

    lowered = filename.lower()
    if lowered.endswith(".nii.gz"):
        file_format = MRIFileFormat.NIFTI_GZ
    elif lowered.endswith(".nii"):
        file_format = MRIFileFormat.NIFTI
    else:
        raise HTTPException(status_code=415, detail="Only .nii and .nii.gz MRI files are supported.")

    stream = upload.file
    stream.seek(0)
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > max_size_bytes:
            stream.seek(0)
            raise HTTPException(status_code=413, detail="MRI file exceeds the configured upload limit.")
    if size == 0:
        stream.seek(0)
        raise HTTPException(status_code=422, detail="MRI file is empty.")

    stream.seek(0)
    try:
        if file_format is MRIFileFormat.NIFTI_GZ:
            with gzip.GzipFile(fileobj=stream, mode="rb") as compressed:
                header = compressed.read(540)
        else:
            header = stream.read(540)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        stream.seek(0)
        raise HTTPException(status_code=422, detail="MRI file is not a valid NIfTI image.") from exc
    finally:
        stream.seek(0)

    if not _is_nifti_header(header):
        raise HTTPException(status_code=422, detail="MRI file is not a valid NIfTI image.")
    return filename, file_format


def _is_nifti_header(header: bytes) -> bool:
    if len(header) >= 348 and int.from_bytes(header[:4], "little") == 348:
        return header[344:348] == _NIFTI1_MAGIC
    if len(header) >= 540 and int.from_bytes(header[:4], "little") == 540:
        return header[4:12] == _NIFTI2_MAGIC
    if len(header) >= 348 and int.from_bytes(header[:4], "big") == 348:
        return header[344:348] == _NIFTI1_MAGIC
    if len(header) >= 540 and int.from_bytes(header[:4], "big") == 540:
        return header[4:12] == _NIFTI2_MAGIC
    return False


def create_and_analyze_study(
    upload: UploadFile,
    owner: User,
    db: Session,
    storage: StorageBackend,
    ml_service: MLService,
    settings: Settings | None = None,
    patient_user_id: int | None = None,
    study_date: date | None = None,
) -> tuple[MRIStudy, Assessment]:
    settings = settings or get_settings()
    original_filename, file_format = validate_nifti_upload(
        upload, settings.max_mri_upload_size_mb * 1024 * 1024
    )
    upload.file.seek(0)
    try:
        stored: StoredObject = storage.store(
            upload.file,
            filename=original_filename,
            content_type=upload.content_type,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="MRI file could not be stored.") from exc

    study = MRIStudy(
        owner_user_id=owner.id,
        patient_user_id=patient_user_id,
        study_date=study_date,
        original_filename=stored.original_filename,
        storage_key=stored.key,
        modality="T1",
        file_format=file_format,
        status=MRIStudyStatus.UPLOADED,
    )
    db.add(study)
    try:
        db.commit()
        db.refresh(study)
    except Exception as exc:
        db.rollback()
        storage.delete(stored.key)
        raise HTTPException(status_code=500, detail="MRI study could not be recorded.") from exc

    return analyze_study(study, db, storage, ml_service, settings)


def analyze_study(
    study: MRIStudy,
    db: Session,
    storage: StorageBackend,
    ml_service: MLService,
    settings: Settings | None = None,
) -> tuple[MRIStudy, Assessment]:
    settings = settings or get_settings()
    study.status = MRIStudyStatus.PROCESSING
    study.error_message = None
    db.commit()

    quality_status = InputQualityStatus.ACCEPTABLE
    failure_message: str | None = None
    prediction: MLPrediction | None = None
    suffix = ".nii.gz" if study.file_format is MRIFileFormat.NIFTI_GZ else ".nii"
    temporary_path: Path | None = None

    try:
        with storage.open(study.storage_key) as source:
            with tempfile.NamedTemporaryFile(prefix="cystguard-mri-", suffix=suffix, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                shutil.copyfileobj(source, temporary, length=1024 * 1024)
        prediction = ml_service.analyze(temporary_path)
        if not isinstance(prediction, MLPrediction):
            raise ModelInferenceError("Cyst-X returned an invalid result.")
    except ModelConfigurationError as exc:
        failure_message = str(exc)
        if settings.cystx_diagnostics_enabled:
            logger.exception(
                "Cyst-X setup failed; model_executed=false fallback_used=false."
            )
    except FileNotFoundError:
        quality_status = InputQualityStatus.NOT_EVALUATED
        failure_message = "Stored MRI file is unavailable; no prediction was produced."
        if settings.cystx_diagnostics_enabled:
            logger.exception(
                "Cyst-X input file was unavailable; model_executed=false fallback_used=false."
            )
    except Exception:
        failure_message = "Cyst-X inference failed; no prediction was produced."
        if settings.cystx_diagnostics_enabled:
            logger.exception(
                "Cyst-X inference failed; model_executed status depends on the failing stage; "
                "fallback_used=false."
            )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    if prediction is None:
        if failure_message is None:
            failure_message = "Cyst-X inference failed; no prediction was produced."
        study.status = MRIStudyStatus.FAILED
        study.error_message = failure_message
        assessment = Assessment(
            mri_study_id=study.id,
            model_id="cystx",
            model_version=settings.cystx_model_version,
            architecture="3D DenseNet-121",
            risk_class=None,
            raw_score=None,
            threshold=None,
            prediction_status=PredictionStatus.FAILED,
            input_quality_status=quality_status,
            fallback_used=False,
            error_message=failure_message,
        )
    else:
        study.status = MRIStudyStatus.ANALYZED
        study.error_message = None
        assessment = Assessment(
            mri_study_id=study.id,
            model_id=prediction.model_id,
            model_version=prediction.model_version,
            architecture=prediction.architecture,
            risk_class=prediction.risk_class,
            raw_score=prediction.raw_score,
            threshold=prediction.threshold,
            prediction_status=PredictionStatus.SUCCESS,
            input_quality_status=InputQualityStatus.ACCEPTABLE,
            fallback_used=False,
            error_message=None,
        )

    db.add(assessment)
    db.commit()
    db.refresh(study)
    db.refresh(assessment)
    return study, assessment


def get_accessible_study(db: Session, study_id: str, user: User) -> MRIStudy:
    """Read a study owned by the caller or linked to a patient granting access.

    Unlinked historical studies remain owner-only. Once a study is linked to a
    patient, an active patient-doctor grant is required even for its uploader.
    """
    study = db.get(MRIStudy, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="MRI study not found.")
    if study.patient_user_id is not None:
        require_patient_access(db, user, study.patient_user_id)
    elif user.role is not UserRole.DOCTOR or study.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="MRI study not found.")
    return study


def get_accessible_assessment(db: Session, assessment_id: str, user: User) -> Assessment:
    assessment = db.scalar(
        select(Assessment)
        .join(MRIStudy, Assessment.mri_study_id == MRIStudy.id)
        .where(Assessment.id == assessment_id)
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    get_accessible_study(db, assessment.mri_study_id, user)
    return assessment


def get_latest_assessment(study: MRIStudy) -> Assessment:
    if not study.assessments:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return study.assessments[-1]
