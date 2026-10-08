"""
CystGuard Cyst-X preprocessing.

This follows the official Cyst-X test preprocessing pipeline:

    EnsureChannelFirst -> Resize(96, 96, 96)

No additional normalization, cropping, or augmentation is applied.
"""

from monai.transforms import Compose, EnsureChannelFirst, Resize


def get_cystx_test_transforms():
    """
    Return the preprocessing pipeline used for Cyst-X inference.
    """
    return Compose(
        [
            EnsureChannelFirst(),
            Resize((96, 96, 96)),
        ]
    )