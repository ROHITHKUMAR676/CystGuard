from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "CystGuard API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./cystguard.db"
    secret_key: str = ""
    access_token_expire_minutes: int = 30
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    storage_root: Path = Path.home() / ".cystguard" / "storage"
    cystx_checkpoint_path: Path | None = None
    cystx_source_path: Path | None = None
    cystx_model_version: str = "cystx-baseline-v1"
    cystx_diagnostics_enabled: bool = False
    foodcnn_checkpoint_path: Path = PROJECT_ROOT / "backend" / "vendor" / "FoodCNN" / "best_finetuned_combined_model.pth"
    foodcnn_model_version: str = "FoodCNN@2c944166f988acff4374d131b8b1fe535a64abf6"
    max_meal_upload_size_mb: int = 12
    max_mri_upload_size_mb: int = 512
    max_document_upload_size_mb: int = 25
    tesseract_cmd: str | None = None
    sarvam_api_key: str = ""
    sarvam_api_url: str = "https://api.sarvam.ai/v1/chat/completions"
    sarvam_model: str = "sarvam-105b"
    sarvam_timeout_seconds: float = 12.0

    @field_validator("sarvam_timeout_seconds")
    @classmethod
    def positive_sarvam_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("SARVAM_TIMEOUT_SECONDS must be positive")
        return value

    @property
    def max_mri_upload_size_bytes(self) -> int:
        return self.max_mri_upload_size_mb * 1024 * 1024

    @field_validator("database_url", mode="before")
    @classmethod
    def default_database_for_blank_value(cls, value: object) -> object:
        return "sqlite:///./cystguard.db" if value == "" else value

    @field_validator("access_token_expire_minutes")
    @classmethod
    def positive_token_lifetime(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        return value

    @field_validator("max_mri_upload_size_mb")
    @classmethod
    def positive_mri_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_MRI_UPLOAD_SIZE_MB must be positive")
        return value

    @field_validator("max_document_upload_size_mb")
    @classmethod
    def positive_document_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_DOCUMENT_UPLOAD_SIZE_MB must be positive")
        return value

    @field_validator("max_meal_upload_size_mb")
    @classmethod
    def positive_meal_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_MEAL_UPLOAD_SIZE_MB must be positive")
        return value

    @field_validator("foodcnn_checkpoint_path", mode="before")
    @classmethod
    def resolve_foodcnn_checkpoint(cls, value: object) -> object:
        if value in (None, ""):
            return PROJECT_ROOT / "backend" / "vendor" / "FoodCNN" / "best_finetuned_combined_model.pth"
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @field_validator("storage_root", mode="before")
    @classmethod
    def default_storage_for_blank_value(cls, value: object) -> object:
        return Path.home() / ".cystguard" / "storage" if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
