"""
CystGuard Cyst-X preprocessing.

This follows the official Cyst-X test preprocessing pipeline:

    EnsureChannelFirst -> Resize(96, 96, 96)

No additional normalization, cropping, or augmentation is applied.
"""

from monai.transforms import Compose, EnsureChannelFirst, Resize, ScaleIntensityRangePercentiles


def get_cystx_test_transforms():
    """
    Return the preprocessing pipeline used for Cyst-X inference.
    Normalizes voxel intensities into [0, 1] using robust 1st-99th percentiles
    before resizing to (96, 96, 96).
    """
    return Compose(
        [
            EnsureChannelFirst(),
            ScaleIntensityRangePercentiles(lower=1, upper=99, b_min=0.0, b_max=1.0, clip=True),
            Resize((96, 96, 96)),
        ]
    )