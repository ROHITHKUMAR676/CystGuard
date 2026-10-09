"""
CystGuard model adapter for the Cyst-X baseline.

The adapter provides a stable interface between the backend
and the underlying Cyst-X inference implementation.
"""

from pathlib import Path
from typing import Any

from .cystx_inference import CystXInference


class CystXAdapter:
    """
    Backend-facing adapter for Cyst-X.

    The rest of CystGuard should interact with this adapter
    instead of directly depending on the Cyst-X implementation.
    """

    def __init__(
        self,
        checkpoint_path: str,
        device: str | None = None,
        diagnostics_enabled: bool = False,
    ):
        self.checkpoint_path = Path(checkpoint_path)

        self.engine = CystXInference(
            checkpoint_path=str(self.checkpoint_path),
            device=device,
            diagnostics_enabled=diagnostics_enabled,
        )

    def analyze(self, mri_path: str) -> dict[str, Any]:
        """
        Analyze a T1 MRI using the Cyst-X baseline.
        """

        result = self.engine.predict(mri_path)

        return {
            "model": result["model"],
            "architecture": result["architecture"],
            "modality": result["modality"],
            "score": result["score"],
            "threshold": result["threshold"],
            "profile": result["profile"],
        }