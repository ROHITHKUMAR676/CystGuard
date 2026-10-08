import re

from app.ocr.normalizer import normalize_dosage_form, normalize_frequency, normalize_route, normalize_strength, normalize_whitespace
from app.ocr.provider import OCRResult
from app.schemas.report import DocumentType


_STRENGTH = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|μg|µg|g|IU|units?)\b", re.I)
_FREQUENCY = re.compile(r"\b(once\s+daily|once\s+(?:a|per)\s+day|twice\s+daily|twice\s+a\s+day|two\s+times\s+(?:a\s+)?day|three\s+times\s+daily|three\s+times\s+a\s+day|four\s+times\s+daily|four\s+times\s+a\s+day|bid|tid|qid|(?<!once\s)(?<!twice\s)daily)\b", re.I)
_DOSE = re.compile(r"\b(\d+(?:\.\d+)?\s*(?:tablet|tablets|tab|tabs|capsule|capsules|cap|caps|ml|mL|puff|puffs|drop|drops))\b", re.I)
_ROUTE = re.compile(r"\b(oral|by mouth|intravenous|IV|intramuscular|IM|subcutaneous|SC|topical|inhaled|rectal)\b", re.I)
_FORM = re.compile(r"\b(tablets?|tabs?|capsules?|caps?|oral solution|suspension|injection|inhaler|cream|ointment)\b", re.I)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _source_page(ocr: OCRResult, line: str):
    return next((p for p in ocr.pages if line in p.text), None)


def extract_medication_candidates(ocr: OCRResult, document_id: str) -> list[dict]:
    candidates = []
    for line in (line.strip() for line in ocr.text.splitlines()):
        if not line:
            continue
        strength_match = _STRENGTH.search(line)
        explicit = re.match(r"(?i)^\s*(?:medication|medicine|drug|brand\s+name|generic\s+name)\s*:\s*(.+)$", line)
        if not strength_match and not explicit:
            continue
        if strength_match:
            prefix = line[:strength_match.start()].strip(" :-\t")
            strength_text = strength_match.group(0)
        else:
            prefix, strength_text = explicit.group(1).strip(), None
        prefix = re.sub(r"(?i)^(?:medication|medicine|drug)\s*:\s*", "", prefix).strip()
        # Keep only an explicitly printed name; no lexicon or pill-image inference is used.
        name = re.split(r"(?i)\b(?:take|dose|frequency|route)\s*[:=]", prefix)[0].strip(" :-") or None
        if not name:
            continue
        generic = None
        brand = None
        lower = line.lower()
        if lower.startswith("generic name:"):
            generic = name
        elif lower.startswith("brand name:"):
            brand = name
        strength, strength_note = normalize_strength(strength_text)
        frequency_match = _FREQUENCY.search(line)
        frequency, frequency_note = normalize_frequency(frequency_match.group(0)) if frequency_match else (None, None)
        dose_match = _DOSE.search(line)
        form_match = _FORM.search(line)
        dosage_form, form_note = normalize_dosage_form(form_match.group(0)) if form_match else (None, None)
        route_match = _ROUTE.search(line)
        route, route_note = normalize_route(route_match.group(0)) if route_match else (None, None)
        start_date_match = re.search(r"(?i)\bstart\s*date\s*[:=]\s*(\d{4}-\d{2}-\d{2})", line)
        end_date_match = re.search(r"(?i)\bend\s*date\s*[:=]\s*(\d{4}-\d{2}-\d{2})", line)
        prescriber_match = re.search(r"(?i)\bprescriber\s*[:=]\s*([^,;]+)", line)
        indication_match = re.search(r"(?i)\bindication\s*[:=]\s*([^,;]+)", line)
        page = _source_page(ocr, line)
        notes = tuple(note for note in (strength_note, frequency_note, form_note, route_note) if note)
        candidates.append({
            "name": name,
            "generic_name": generic,
            "brand_name": brand,
            "strength": strength_text,
            "normalized_strength": strength,
            "dose": dose_match.group(0) if dose_match else None,
            "dosage_form": dosage_form,
            "frequency": frequency_match.group(0) if frequency_match else None,
            "normalized_frequency": frequency,
            "route": route_match.group(0) if route_match else None,
            "normalized_route": route,
            "start_date": start_date_match.group(1) if start_date_match else None,
            "end_date": end_date_match.group(1) if end_date_match else None,
            "duration": re.search(r"(?i)\bfor\s+(\d+\s*(?:days?|weeks?|months?))\b", line).group(1) if re.search(r"(?i)\bfor\s+(\d+\s*(?:days?|weeks?|months?))\b", line) else None,
            "prescriber": prescriber_match.group(1).strip() if prescriber_match else None,
            "indication": indication_match.group(1).strip() if indication_match else None,
            "normalization_notes": notes,
            "source_document_id": document_id,
            "source_type": "OCR_EXTRACTED",
            "page": page.page_number if page else None,
            "source_text": line,
            "extraction_method": ocr.method,
            "extraction_confidence": page.extraction_confidence if page else None,
        })
    return candidates


def normalized_medication_key(candidate: dict) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(candidate.get("generic_name") or candidate.get("name") or "").lower())


def normalize_medication_document_text(text: str) -> str:
    return normalize_whitespace(text)
