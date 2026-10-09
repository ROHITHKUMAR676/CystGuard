import importlib
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import torch
from monai.data import ImageDataset
from monai.transforms import Compose, EnsureChannelFirst, Resize


ML_ROOT = Path(__file__).resolve().parents[2] / "ml"
sys.path.insert(0, str(ML_ROOT))

CystXInference = importlib.import_module("baseline.cystx_inference").CystXInference
get_cystx_test_transforms = importlib.import_module(
    "baseline.preprocessing"
).get_cystx_test_transforms


def test_preprocessing_matches_official_test_transform_without_intensity_scaling(tmp_path):
    values = np.arange(24 * 20 * 16, dtype=np.float32).reshape(24, 20, 16) + 1000
    image_path = tmp_path / "known-range.nii.gz"
    nib.save(nib.Nifti1Image(values, np.eye(4)), str(image_path))

    cystguard_tensor = ImageDataset(
        image_files=[str(image_path)],
        transform=get_cystx_test_transforms(),
    )[0]
    official_tensor = ImageDataset(
        image_files=[str(image_path)],
        transform=Compose([EnsureChannelFirst(), Resize((96, 96, 96))]),
    )[0]

    torch.testing.assert_close(cystguard_tensor, official_tensor)
    assert tuple(cystguard_tensor.shape) == (1, 96, 96, 96)
    assert cystguard_tensor.dtype == torch.float32
    assert float(cystguard_tensor.min()) >= 1000
    assert float(cystguard_tensor.max()) > 1


def test_controlled_logits_map_to_official_binary_target():
    cases = [
        (-2.0, "NO_LOW_RISK"),
        (0.0, "HIGH_RISK"),
        (2.0, "HIGH_RISK"),
    ]
    for raw_logit, expected_profile in cases:
        score, profile = CystXInference._interpret_logit(torch.tensor([raw_logit]))
        assert profile == expected_profile
        assert (score >= 0.5) == (expected_profile == "HIGH_RISK")


def test_input_diagnostics_report_metadata_and_non_finite_counts(tmp_path):
    values = np.full((4, 5, 6), 7.0, dtype=np.float32)
    values[0, 0, 0] = np.nan
    values[0, 0, 1] = np.inf
    affine = np.diag([0.8, 1.2, 2.5, 1.0])
    image_path = tmp_path / "diagnostic-volume.nii"
    nib.save(nib.Nifti1Image(values, affine), str(image_path))

    inference = object.__new__(CystXInference)
    diagnostic = inference._input_volume_diagnostics(image_path)

    assert diagnostic["shape"] == [4, 5, 6]
    np.testing.assert_allclose(diagnostic["voxel_spacing_mm"], [0.8, 1.2, 2.5])
    assert diagnostic["orientation"] == ["R", "A", "S"]
    assert diagnostic["intensity"]["constant_volume"] is True
    assert diagnostic["intensity"]["finite_voxels"] == values.size - 2
    assert diagnostic["intensity"]["non_finite_voxels"] == 2
    assert diagnostic["modality_verified"] is False
