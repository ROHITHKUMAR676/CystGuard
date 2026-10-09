"""
CystGuard Cyst-X preprocessing.

This follows the official Cyst-X centralized binary-classification test pipeline:

    EnsureChannelFirst -> Resize(96, 96, 96)

No intensity normalization, cropping, or augmentation is applied.
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