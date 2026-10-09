from dataclasses import dataclass
from functools import lru_cache
import importlib
import math
from pathlib import Path
import sys
from threading import RLock
from typing import Protocol

from app.config import Settings, get_settings


class ModelConfigurationError(RuntimeError):
    """The Cyst-X model cannot be initialized from the configured environment."""


class ModelInferenceError(RuntimeError):
    """Cyst-X returned an unusable inference result."""


@dataclass(frozen=True)
class MLPrediction:
    model_id: str
    model_version: str
    risk_class: str
    raw_score: float
    threshold: float
    architecture: str = "3D DenseNet-121"


class MLService(Protocol):
    def analyze(self, mri_path: Path) -> MLPrediction: ...


_IMPORT_LOCK = RLock()


@lru_cache(maxsize=4)
def _load_adapter(checkpoint_path: str, source_path: str, diagnostics_enabled: bool = False):
    checkpoint = Path(checkpoint_path).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    if not checkpoint.is_file():
        raise ModelConfigurationError("Configured Cyst-X checkpoint is unavailable.")
    if not source.is_dir() or not (source / "model.py").is_file() and not (source / "model" / "__init__.py").is_file():
        raise ModelConfigurationError(
            "CYSTX_SOURCE_PATH must point to the official Cyst-X source directory containing model.get_model."
        )

    repository_ml = Path(__file__).resolve().parents[3] / "ml"
    with _IMPORT_LOCK:
        existing_model = sys.modules.get("model")
        existing_file = getattr(existing_model, "__file__", None)
        if existing_file and not Path(existing_file).resolve().is_relative_to(source):
            raise ModelConfigurationError(
                "A different module named 'model' is already loaded; start a clean backend process for Cyst-X."
            )
        for path in (str(source), str(repository_ml)):
            while path in sys.path:
                sys.path.remove(path)
        sys.path[:0] = [str(repository_ml), str(source)]
        try:
            adapter_type = importlib.import_module("baseline.adapter").CystXAdapter
        except (ImportError, ModuleNotFoundError) as exc:
            raise ModelConfigurationError(
                "Cyst-X runtime dependencies are unavailable; install the required PyTorch and MONAI packages."
            ) from exc

    try:
        return adapter_type(
            checkpoint_path=str(checkpoint),
            diagnostics_enabled=diagnostics_enabled,
        )
    except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as exc:
        raise ModelConfigurationError("Cyst-X could not load the configured checkpoint.") from exc


class CystXMLService:
    """Backend-facing Cyst-X interface; the baseline adapter owns model behavior."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def analyze(self, mri_path: Path) -> MLPrediction:
        checkpoint = self.settings.cystx_checkpoint_path
        source = self.settings.cystx_source_path
        if checkpoint is None:
            raise ModelConfigurationError("CYSTX_CHECKPOINT_PATH is not configured.")
        if source is None:
            raise ModelConfigurationError("CYSTX_SOURCE_PATH is not configured.")
        adapter = _load_adapter(
            str(checkpoint),
            str(source),
            diagnostics_enabled=self.settings.cystx_diagnostics_enabled,
        )
        result = adapter.analyze(str(mri_path))
        try:
            raw_score = float(result["score"])
            threshold = float(result["threshold"])
            risk_class = str(result["profile"])
            architecture = str(result["architecture"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelInferenceError("Cyst-X returned an incomplete result.") from exc
        if (
            not math.isfinite(raw_score)
            or not math.isfinite(threshold)
            or not 0.0 <= raw_score <= 1.0
            or not 0.0 <= threshold <= 1.0
            or risk_class not in {"HIGH_RISK", "NO_LOW_RISK"}
            or not architecture.strip()
        ):
            raise ModelInferenceError("Cyst-X returned an invalid score or profile.")
        return MLPrediction(
            model_id="cystx",
            model_version=self.settings.cystx_model_version,
            risk_class=risk_class,
            raw_score=raw_score,
            threshold=threshold,
            architecture=architecture,
        )


def get_ml_service() -> CystXMLService:
    return CystXMLService()
