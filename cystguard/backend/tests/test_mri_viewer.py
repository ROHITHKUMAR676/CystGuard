from io import BytesIO
from types import SimpleNamespace

import pytest

from app.mri.viewer import volume_metadata
from app.mri.viewer import render_slice
from app.mri.models import MRIFileFormat


class FakeImage:
    shape = (64, 48, 32)

    class Header:
        def get_zooms(self):
            return (0.8, 0.8, 1.2)

    header = Header()


def test_viewer_metadata_reports_planes_and_no_overlay(monkeypatch):
    from app.mri import viewer
    monkeypatch.setattr(viewer, "_load", lambda study, storage: (FakeImage(), __import__("pathlib").Path("missing-temp.nii")))
    study = SimpleNamespace(id="study-1", modality="T1")
    metadata = volume_metadata(study, object())
    assert metadata["dimensions"] == (64, 48, 32)
    assert metadata["planes"]["axial"]["slice_count"] == 32
    assert metadata["planes"]["coronal"]["slice_count"] == 48
    assert metadata["planes"]["sagittal"]["slice_count"] == 64
    assert metadata["overlay_available"] is False
    assert metadata["overlay_source"] is None


def test_viewer_metadata_parse_failure_is_explicit(monkeypatch):
    from app.mri import viewer
    def fail(study, storage):
        raise ValueError("Stored MRI volume cannot be parsed")
    monkeypatch.setattr(viewer, "_load", fail)
    with pytest.raises(ValueError, match="cannot be parsed"):
        volume_metadata(SimpleNamespace(id="study-1", modality="T1"), object())


def test_real_nifti_slice_is_rendered_as_png_without_overlay(tmp_path):
    import nibabel as nib
    import numpy as np

    path = tmp_path / "volume.nii"
    nib.save(nib.Nifti1Image(np.arange(8 * 9 * 10, dtype=np.float32).reshape(8, 9, 10), np.eye(4)), path)
    content = path.read_bytes()

    class Storage:
        def open(self, key):
            return BytesIO(content)

    study = SimpleNamespace(id="viewer-study", modality="T1", file_format=MRIFileFormat.NIFTI, storage_key="opaque")
    image = render_slice(study, Storage(), "axial", 4)
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    metadata = volume_metadata(study, Storage())
    assert metadata["overlay_available"] is False
    assert metadata["dimensions"] == (8, 9, 10)
