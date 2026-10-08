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

from pathlib import Path
from typing import Any

import torch
from monai.data import ImageDataset

from .preprocessing import get_cystx_test_transforms

# The official Cyst-X repository provides get_model().
#
# The official Cyst-X source directory must be available
# on PYTHONPATH when this module is used.
from model import get_model


class CystXInference:
    """
    Inference wrapper for the official Cyst-X DenseNet-121 model.
    """

    def __init__(
        self,
        checkpoint_path: str,
        device: str | None = None,
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

    def _load_model(self) -> torch.nn.Module:
        """
        Load the official Cyst-X DenseNet-121 checkpoint.
        """

        model = get_model(
            name="densenet121",
            num_classes=1,
        )

        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=self.device,
        )

        model.load_state_dict(checkpoint)

        model.to(self.device)
        model.eval()

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
        dataset = ImageDataset(
            image_files=[str(mri_path)],
            transform=self.transforms,
        )

        image = dataset[0]

        # ImageDataset returns a single image tensor.
        # Add batch dimension for DenseNet.
        image = image.unsqueeze(0).to(self.device)

        with torch.no_grad():
            logit = self.model(image)

            score = torch.sigmoid(logit).item()

        profile = (
            "HIGH_RISK"
            if score >= 0.5
            else "NO_LOW_RISK"
        )

        return {
            "model": "Cyst-X",
            "architecture": "3D DenseNet-121",
            "modality": "T1",
            "input_shape": [96, 96, 96],
            "logit": float(logit.item()),
            "score": float(score),
            "threshold": 0.5,
            "profile": profile,
            "device": str(self.device),
        }