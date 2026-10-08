from dataclasses import dataclass
from io import BytesIO
from typing import Protocol


class OCRProviderError(RuntimeError):
    """OCR provider is unavailable or cannot process the supplied document."""


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
        values = [p.extraction_confidence for p in self.pages if p.extraction_confidence is not None]
        return sum(values) / len(values) if values else None


class OCRProvider(Protocol):
    def extract(self, content: bytes, media_type: str) -> OCRResult: ...


class LocalOCRProvider:
    """Extract selectable PDF text and run local Tesseract on images/scanned PDF pages."""

    def extract(self, content: bytes, media_type: str) -> OCRResult:
        if media_type == "application/pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise OCRProviderError("PDF text extraction requires the optional backend OCR dependencies.") from exc
            try:
                reader = PdfReader(BytesIO(content), strict=True)
                if reader.is_encrypted:
                    raise OCRProviderError("Encrypted PDF documents are not supported.")
                if len(reader.pages) > 100:
                    raise OCRProviderError("PDF exceeds the 100-page processing limit.")
                extracted = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
                if not extracted:
                    raise OCRProviderError("PDF contains no pages.")
                scanned_pages = [number for number, text in extracted if not text.strip()]
                if not scanned_pages:
                    return OCRResult(pages=tuple(OCRPage(number, text) for number, text in extracted), method="pypdf-text")
                try:
                    import fitz
                    from PIL import Image
                    import pytesseract
                    from pytesseract import Output
                except ImportError as exc:
                    raise OCRProviderError("Scanned PDF pages require PyMuPDF, Pillow, pytesseract, and Tesseract.") from exc
                try:
                    pdf = fitz.open(stream=content, filetype="pdf")
                    for number in scanned_pages:
                        pixmap = pdf[number - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                        data = pytesseract.image_to_data(image, output_type=Output.DICT)
                        tokens = []
                        for item in data.get("conf", []):
                            try:
                                confidence = float(item)
                            except (TypeError, ValueError):
                                continue
                            if confidence >= 0:
                                tokens.append(confidence / 100.0)
                        confidence = sum(tokens) / len(tokens) if tokens else None
                        extracted[number - 1] = (number, pytesseract.image_to_string(image), confidence)
                    pdf.close()
                except OCRProviderError:
                    raise
                except Exception as exc:
                    raise OCRProviderError("Scanned PDF OCR failed.") from exc
                pages = tuple(
                    OCRPage(item[0], item[1], item[2] if len(item) > 2 else None)
                    for item in extracted
                )
                return OCRResult(pages=pages, method="pypdf-text+tesseract-local")
            except OCRProviderError:
                raise
            except Exception as exc:
                raise OCRProviderError("PDF text extraction failed.") from exc
        try:
            from PIL import Image, UnidentifiedImageError
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise OCRProviderError("Image OCR requires Pillow, pytesseract, and the Tesseract executable.") from exc
        try:
            with Image.open(BytesIO(content)) as image:
                image.load()
                data = pytesseract.image_to_data(image, output_type=Output.DICT)
                text = pytesseract.image_to_string(image)
                confidences = []
                for value in data.get("conf", []):
                    try:
                        numeric = float(value)
                    except (ValueError, TypeError):
                        continue
                    if numeric >= 0:
                        confidences.append(numeric / 100.0)
                confidence = sum(confidences) / len(confidences) if confidences else None
                return OCRResult((OCRPage(1, text, confidence),), "tesseract-local")
        except UnidentifiedImageError as exc:
            raise OCRProviderError("Image could not be decoded.") from exc
        except OCRProviderError:
            raise
        except Exception as exc:
            raise OCRProviderError("Local image OCR failed.") from exc


def get_ocr_provider() -> OCRProvider:
    return LocalOCRProvider()
