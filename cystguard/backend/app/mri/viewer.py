import shutil
import struct
import tempfile
import zlib
from pathlib import Path

from app.mri.models import MRIStudy
from app.storage.service import StorageBackend


PLANES = {"sagittal": 0, "coronal": 1, "axial": 2}


def _load(study: MRIStudy, storage: StorageBackend):
    try:
        import nibabel as nib
    except ImportError as exc:
        raise ValueError("MRI viewer dependencies are unavailable") from exc
    suffix = ".nii.gz" if study.file_format.value == "NIFTI_GZ" else ".nii"
    temporary_path: Path | None = None
    try:
        with storage.open(study.storage_key) as source:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as target:
                temporary_path = Path(target.name)
                shutil.copyfileobj(source, target)
        image = nib.as_closest_canonical(nib.load(str(temporary_path)))
        if len(image.shape) < 3 or any(int(dim) < 1 for dim in image.shape[:3]):
            raise ValueError("MRI volume must have three non-empty spatial dimensions")
        return image, temporary_path
    except Exception as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ValueError("Stored MRI volume cannot be parsed") from exc


def volume_metadata(study: MRIStudy, storage: StorageBackend) -> dict:
    image, temporary_path = _load(study, storage)
    try:
        shape = tuple(int(value) for value in image.shape[:3])
        spacing = tuple(round(float(value), 4) for value in image.header.get_zooms()[:3])
        return {
            "study_id": study.id,
            "modality": study.modality,
            "dimensions": shape,
            "spacing_mm": spacing,
            "planes": {name: {"axis": axis, "slice_count": shape[axis]} for name, axis in PLANES.items()},
            "overlay_available": False,
            "overlay_source": None,
        }
    finally:
        temporary_path.unlink(missing_ok=True)


def render_slice(study: MRIStudy, storage: StorageBackend, plane: str, index: int) -> bytes:
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("MRI viewer dependencies are unavailable") from exc
    if plane not in PLANES:
        raise ValueError("Unsupported MRI plane")
    image, temporary_path = _load(study, storage)
    try:
        axis = PLANES[plane]
        count = int(image.shape[axis])
        if index < 0 or index >= count:
            raise IndexError("Slice index is outside the volume")
        selectors = [slice(None)] * len(image.shape)
        selectors[axis] = index
        if len(selectors) > 3:
            selectors[3] = 0
        section = np.asarray(image.dataobj[tuple(selectors)])
        section = np.rot90(section)
        finite = section[np.isfinite(section)]
        if finite.size == 0:
            raise ValueError("MRI slice contains no displayable voxel values")
        low, high = np.percentile(finite, (1, 99))
        if high <= low:
            high = low + 1
        pixels = np.clip((section.astype(np.float32) - low) * (255.0 / (high - low)), 0, 255)
        pixels[~np.isfinite(pixels)] = 0
        raster = pixels.astype(np.uint8)
        height, width = raster.shape
        rows = b"".join(b"\x00" + raster[row].tobytes() for row in range(height))

        def chunk(kind: bytes, data: bytes) -> bytes:
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
    finally:
        temporary_path.unlink(missing_ok=True)
