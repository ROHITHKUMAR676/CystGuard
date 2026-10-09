"""
CystGuard Cyst-X baseline inference.

This module wraps the official Cyst-X 3D DenseNet-121 model
for T1-weighted pancreatic MRI risk classification.

Official Cyst-X inference pipeline:

    T1 MRI (.nii/.nii.gz)
        ↓
    EnsureChannelFirst
        ↓
    Resize(96, 96, 96)
        ↓
    3D DenseNet-121
        ↓
    Logit
        ↓
    Sigmoid score
        ↓
    Binary risk profile

Important:
    The sigmoid output is a Cyst-X model score.
    It must NOT be interpreted as a calibrated probability
    of cancer.

CystGuard is a research prototype and does not provide
autonomous diagnosis or treatment decisions.
"""

import hashlib
import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from monai.data import ImageDataset

from .preprocessing import get_cystx_test_transforms

logger = logging.getLogger(__name__)
_THRESHOLD = 0.5


class CystXInference:
    """
    Inference wrapper for the official Cyst-X DenseNet-121 model.
    """

    def __init__(
        self,
        checkpoint_path: str,
        device: str | None = None,
        diagnostics_enabled: bool = False,
    ):
        """
        Initialize the Cyst-X inference engine.

        Args:
            checkpoint_path:
                Path to the official Cyst-X model checkpoint.

            device:
                Device to use for inference.
                If omitted, CUDA is used when available,
                otherwise CPU.
        """

        self.checkpoint_path = Path(checkpoint_path)
        self.diagnostics_enabled = diagnostics_enabled

        if not self.checkpoint_path.exists():
            raise FileNotFoundError(
                f"Cyst-X checkpoint not found: "
                f"{self.checkpoint_path}"
            )

        self.device = torch.device(
            device
            if device
            else (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        )

        self.transforms = get_cystx_test_transforms()

        self.model = self._load_model()

    def _log_diagnostics(self, event: str, **details: Any) -> None:
        if self.diagnostics_enabled:
            payload = {"event": event, **details}
            logger.info("cystx_diagnostics %s", json.dumps(payload, sort_keys=True, allow_nan=False))

    @staticmethod
    def _checkpoint_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as checkpoint_file:
            for chunk in iter(lambda: checkpoint_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _input_volume_diagnostics(self, mri_path: Path) -> dict[str, Any]:
        import nibabel as nib

        volume = nib.load(str(mri_path))
        data = np.asanyarray(volume.dataobj)
        finite = np.isfinite(data)
        finite_data = data[finite]

        def finite_number(value: float) -> float | None:
            number = float(value)
            return number if math.isfinite(number) else None

        return {
            "shape": [int(value) for value in volume.shape],
            "affine": [
                [finite_number(value) for value in row]
                for row in np.asarray(volume.affine, dtype=np.float64)
            ],
            "voxel_spacing_mm": [
                finite_number(value) for value in volume.header.get_zooms()[:3]
            ],
            "orientation": list(nib.aff2axcodes(volume.affine)),
            "intensity": {
                "minimum": finite_number(finite_data.min()) if finite_data.size else None,
                "maximum": finite_number(finite_data.max()) if finite_data.size else None,
                "mean": finite_number(finite_data.mean()) if finite_data.size else None,
                "standard_deviation": finite_number(finite_data.std()) if finite_data.size else None,
                "constant_volume": bool(finite_data.min() == finite_data.max()) if finite_data.size else None,
                "finite_voxels": int(finite.sum()),
                "non_finite_voxels": int(data.size - finite.sum()),
            },
            "expected_modality": "T1",
            "modality_verified": False,
        }

    @staticmethod
    def _interpret_logit(logit: torch.Tensor) -> tuple[float, str]:
        score = float(torch.sigmoid(logit).item())
        profile = "HIGH_RISK" if score >= _THRESHOLD else "NO_LOW_RISK"
        return score, profile

    def _load_model(self) -> torch.nn.Module:
        """
        Load the official Cyst-X DenseNet-121 checkpoint.
        """

        # The official Cyst-X source directory is added to sys.path by the backend.
        from model import get_model

        model = get_model(
            name="densenet121",
            num_classes=1,
        )

        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=self.device,
            weights_only=True,
        )

        expected_state = model.state_dict()
        checkpoint_keys = set(checkpoint)
        expected_keys = set(expected_state)
        missing_keys = sorted(expected_keys - checkpoint_keys)
        unexpected_keys = sorted(checkpoint_keys - expected_keys)
        shape_mismatches = sorted(
            key
            for key in expected_keys & checkpoint_keys
            if not hasattr(checkpoint[key], "shape")
            or tuple(checkpoint[key].shape) != tuple(expected_state[key].shape)
        )
        if self.diagnostics_enabled:
            self._log_diagnostics(
                "checkpoint_load",
                checkpoint_name=self.checkpoint_path.name,
                checkpoint_sha256=self._checkpoint_sha256(self.checkpoint_path),
                checkpoint_bytes=self.checkpoint_path.stat().st_size,
                checkpoint_format=type(checkpoint).__name__,
                architecture="MONAI 3D DenseNet-121",
                expected_state_entries=len(expected_state),
                checkpoint_state_entries=len(checkpoint_keys),
                missing_keys=missing_keys,
                unexpected_keys=unexpected_keys,
                shape_mismatches=shape_mismatches,
                strict=True,
            )
        if missing_keys or unexpected_keys or shape_mismatches:
            raise RuntimeError(
                "Cyst-X checkpoint is incompatible with the configured DenseNet-121 model "
                f"(missing={len(missing_keys)}, unexpected={len(unexpected_keys)}, "
                f"shape_mismatches={len(shape_mismatches)})."
            )

        load_result = model.load_state_dict(checkpoint, strict=True)

        model.to(self.device)
        model.eval()
        self._log_diagnostics(
            "model_ready",
            architecture="MONAI 3D DenseNet-121",
            output_shape=[1],
            device=str(self.device),
            evaluation_mode=not model.training,
            missing_keys=list(load_result.missing_keys),
            unexpected_keys=list(load_result.unexpected_keys),
        )

        return model

    def predict(
        self,
        mri_path: str,
    ) -> dict[str, Any]:
        """
        Run Cyst-X inference on a T1-weighted MRI.

        Args:
            mri_path:
                Path to a .nii or .nii.gz MRI file.

        Returns:
            Dictionary containing the Cyst-X model output.
        """

        mri_path = Path(mri_path)

        if not mri_path.exists():
            raise FileNotFoundError(
                f"MRI file not found: {mri_path}"
            )

        if mri_path.suffix not in {".nii", ".gz"}:
            raise ValueError(
                "Cyst-X expects a NIfTI MRI file "
                "(.nii or .nii.gz)."
            )

        # Use MONAI ImageDataset exactly as in the
        # official Cyst-X test pipeline.
        if self.diagnostics_enabled:
            try:
                self._log_diagnostics(
                    "input_volume",
                    **self._input_volume_diagnostics(mri_path),
                )
            except Exception as exc:
                logger.exception(
                    "Cyst-X input diagnostics failed; inference will continue."
                )
                self._log_diagnostics(
                    "input_diagnostics_failed",
                    exception_type=type(exc).__name__,
                )

        try:
            dataset = ImageDataset(
                image_files=[str(mri_path)],
                transform=self.transforms,
            )

            image = dataset[0]

            # ImageDataset returns a single image tensor.
            # Add batch dimension for DenseNet.
            image = image.unsqueeze(0).to(self.device)
        except Exception:
            if self.diagnostics_enabled:
                logger.exception(
                    "Cyst-X input loading/preprocessing failed; "
                    "model_executed=false fallback_used=false."
                )
            raise

        if self.diagnostics_enabled:
            tensor = image.detach().to(device="cpu", dtype=torch.float64)
            finite = torch.isfinite(tensor)
            finite_tensor = tensor[finite]
            self._log_diagnostics(
                "model_input",
                shape=list(image.shape),
                dtype=str(image.dtype),
                device=str(image.device),
                minimum=float(finite_tensor.min()) if finite_tensor.numel() else None,
                maximum=float(finite_tensor.max()) if finite_tensor.numel() else None,
                mean=float(finite_tensor.mean()) if finite_tensor.numel() else None,
                standard_deviation=float(finite_tensor.std(unbiased=False)) if finite_tensor.numel() else None,
                finite_values=int(finite.sum()),
                non_finite_values=int(image.numel() - finite.sum()),
            )

        try:
            with torch.no_grad():
                logit = self.model(image)
                score, profile = self._interpret_logit(logit)
                raw_logit = float(logit.item())
        except Exception:
            if self.diagnostics_enabled:
                logger.exception(
                    "Cyst-X model forward/output interpretation failed; "
                    "model_execution_started=true fallback_used=false."
                )
            raise

        if self.diagnostics_enabled:
            self._log_diagnostics(
                "inference_result",
                model_executed=True,
                fallback_used=False,
                raw_logit=raw_logit if math.isfinite(raw_logit) else None,
                score=score if math.isfinite(score) else None,
                threshold=_THRESHOLD,
                profile=profile,
            )

        return {
            "model": "Cyst-X",
            "architecture": "3D DenseNet-121",
            "modality": "T1",
            "input_shape": [96, 96, 96],
            "logit": raw_logit,
            "score": float(score),
            "threshold": _THRESHOLD,
            "profile": profile,
            "device": str(self.device),
        }