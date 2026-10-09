from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from app.config import get_settings


class OCRProviderError(RuntimeError):
    """The local OCR runtime is unavailable or cannot process the document."""


@dataclass(frozen=True)
class OCRPage:
    page_number: int | None
    text: str
    extraction_confidence: float | None = None


@dataclass(frozen=True)
class OCRResult:
    pages: tuple[OCRPage, ...]
    method: str

    @property
    def text(self) -> str:
        return "\n\f\n".join(page.text for page in self.pages)

    @property
    def extraction_confidence(self) -> float | None:
        values = [page.extraction_confidence for page in self.pages if page.extraction_confidence is not None]
        return sum(values) / len(values) if values else None


class OCRProvider(Protocol):
    def extract(self, content: bytes, media_type: str) -> OCRResult: ...


def _text_quality(text: str) -> int:
    return sum(character.isalnum() for character in text)


class LocalOCRProvider:
    """Extract embedded PDF text and OCR image/scanned pages locally with Tesseract."""

    max_pages = 100
    tesseract_config = "--oem 3 --psm 6"

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        self.tesseract_cmd = tesseract_cmd

    def _ocr_image(self, image, *, page_number: int) -> OCRPage:
        try:
            from PIL import ImageOps
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise OCRProviderError(
                "Image OCR needs Pillow and pytesseract. Install backend/requirements.txt."
            ) from exc

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        try:
            prepared = ImageOps.exif_transpose(image).convert("RGB")
            data = pytesseract.image_to_data(prepared, output_type=Output.DICT, config=self.tesseract_config)
            text = pytesseract.image_to_string(prepared, config=self.tesseract_config)
        except pytesseract.pytesseract.TesseractNotFoundError as exc:
            raise OCRProviderError(
                "Tesseract is not installed or not on PATH. Install the Tesseract executable or set TESSERACT_CMD."
            ) from exc
        except Exception as exc:
            raise OCRProviderError("Local Tesseract OCR failed to process the image.") from exc

        confidences = []
        for value in data.get("conf", []):
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric >= 0:
                confidences.append(numeric / 100.0)
        confidence = sum(confidences) / len(confidences) if confidences else None
        return OCRPage(page_number, text, confidence)

    def _extract_pdf(self, content: bytes) -> OCRResult:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise OCRProviderError(
                "PDF extraction needs pypdf. Install the backend requirements."
            ) from exc

        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise OCRProviderError("Encrypted PDF documents are not supported.")
            if len(reader.pages) > self.max_pages:
                raise OCRProviderError(f"PDF exceeds the {self.max_pages}-page processing limit.")
            if not reader.pages:
                raise OCRProviderError("PDF contains no pages.")
            pages = [OCRPage(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
        except OCRProviderError:
            raise
        except Exception as exc:
            raise OCRProviderError("PDF text extraction failed; the PDF may be damaged or unsupported.") from exc

        # Some scanned PDFs contain a tiny hidden text layer (such as page numbers).
        # OCR pages whose embedded text is too sparse, then keep whichever layer
        # produced more readable text without combining duplicate strings.
        sparse_pages = [index for index, page in enumerate(pages) if _text_quality(page.text) < 30]
        if not sparse_pages:
            return OCRResult(tuple(pages), "pypdf-text")

        try:
            import pymupdf
            from PIL import Image
        except ImportError as exc:
            raise OCRProviderError(
                "Scanned PDF pages need PyMuPDF, Pillow, pytesseract, and the Tesseract executable. "
                "Install backend/requirements.txt and the Tesseract executable."
            ) from exc

        used_tesseract = False
        try:
            pdf = pymupdf.open(stream=content, filetype="pdf")
            for index in sparse_pages:
                pixmap = pdf[index].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                scanned = self._ocr_image(image, page_number=index + 1)
                if _text_quality(scanned.text) > _text_quality(pages[index].text):
                    pages[index] = scanned
                    used_tesseract = True
            pdf.close()
        except OCRProviderError:
            raise
        except Exception as exc:
            raise OCRProviderError("Scanned PDF rendering or OCR failed.") from exc

        method = "pypdf-text+tesseract-local" if used_tesseract else "pypdf-text"
        return OCRResult(tuple(pages), method)

    def _extract_image(self, content: bytes) -> OCRResult:
        try:
            from PIL import Image, ImageSequence, UnidentifiedImageError
        except ImportError as exc:
            raise OCRProviderError(
                "Image decoding needs Pillow. Install backend/requirements.txt."
            ) from exc
        try:
            with Image.open(BytesIO(content)) as image:
                frame_count = getattr(image, "n_frames", 1)
                if frame_count > self.max_pages:
                    raise OCRProviderError(f"Image document exceeds the {self.max_pages}-page processing limit.")
                pages = tuple(self._ocr_image(frame.copy(), page_number=index + 1)
                              for index, frame in enumerate(ImageSequence.Iterator(image)))
                if not pages:
                    raise OCRProviderError("Image document contains no readable frames.")
                method = "tesseract-local" if frame_count == 1 else "tesseract-local-multipage"
                return OCRResult(pages, method)
        except UnidentifiedImageError as exc:
            raise OCRProviderError("Image could not be decoded.") from exc
        except OCRProviderError:
            raise
        except Exception as exc:
            raise OCRProviderError("Local image OCR failed.") from exc

    def extract(self, content: bytes, media_type: str) -> OCRResult:
        if media_type == "application/pdf":
            return self._extract_pdf(content)
        if media_type in {"image/png", "image/jpeg", "image/tiff", "image/bmp"}:
            return self._extract_image(content)
        raise OCRProviderError("Unsupported OCR media type.")


def get_ocr_provider() -> OCRProvider:
    return LocalOCRProvider(tesseract_cmd=get_settings().tesseract_cmd)
