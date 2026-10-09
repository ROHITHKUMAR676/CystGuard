import re

from app.ocr.normalizer import normalize_dosage_form, normalize_frequency, normalize_route, normalize_strength, normalize_whitespace
from app.ocr.provider import OCRResult


_UNIT = r"(?:mg|mcg|[\u03bc\u00b5]g|g|IU|units?)"
_STRENGTH = re.compile(rf"\b(\d+(?:\.\d+)?)\s*({_UNIT})\b", re.I)
_FREQUENCY = re.compile(
    r"\b(once\s+daily|once\s+(?:a|per)\s+day|twice\s+daily|twice\s+a\s+day|"
    r"two\s+times\s+(?:a\s+)?day|three\s+times\s+daily|three\s+times\s+a\s+day|"
    r"four\s+times\s+daily|four\s+times\s+a\s+day|every\s+\d+\s+hours?|"
    r"(?:once\s+)?daily|bid|tid|qid|prn|as\s+needed)\b",
    re.I,
)
_DOSE = re.compile(
    r"\b(\d+(?:\.\d+)?\s*(?:tablets?|tabs?|capsules?|caps?|mL|ml|puffs?|drops?))\b", re.I
)
_ROUTE = re.compile(
    r"\b(by\s+mouth|oral|intravenous|IV|intramuscular|IM|subcutaneous|SC|topical|"
    r"inhaled|inhalation|rectal|ophthalmic|otic|sublingual|buccal|transdermal)\b", re.I
)
_FORM = re.compile(
    r"\b(oral\s+solution|extended-release\s+tablet|delayed-release\s+tablet|"
    r"tablets?|tabs?|capsules?|caps?|suspension|solution|injection|inhaler|"
    r"cream|ointment|patch|suppository|drops?)\b", re.I
)
_NAME_LABEL = re.compile(
    r"^\s*(?:(?:\d+)[.)]\s*)?(?:medication(?:\s+name)?|medicine|drug(?:\s+name)?|"
    r"brand\s+name|generic\s+name|name)\s*[:=\-]\s*(.+)$", re.I
)
_DATE = r"(\d{4}-\d{2}-\d{2})"


def _source_page(ocr: OCRResult, line: str):
    return next((page for page in ocr.pages if line in page.text), None)


def _printed_name(prefix: str) -> str | None:
    """Remove visible instruction syntax while retaining only a printed name."""
    value = re.sub(r"^\s*(?:\d+[.)]\s*)+", "", prefix).strip(" :-\t")
    value = re.sub(r"(?i)^(?:medication(?:\s+name)?|medicine|drug(?:\s+name)?|name)\s*[:=\-]\s*", "", value)
    value = re.sub(r"(?i)^(?:take|use|apply|administer)\s+", "", value)
    value = re.sub(r"(?i)^\d+(?:\.\d+)?\s+(?:tablets?|tabs?|capsules?|caps?)\s+(?:of\s+)?", "", value)
    value = re.sub(r"(?i)^(?:a|an)\s+(?:tablet|capsule)\s+of\s+", "", value)
    value = re.split(
        r"(?i)\b(?:take|use|apply|dose|frequency|route|start\s+date|end\s+date|"
        r"prescriber|indication)\s*[:=]",
        value,
    )[0]
    value = re.split(r"(?i)\b(?:once|twice|three times|four times|every\s+\d+)\b", value)[0]
    value = re.split(r"\b\d+(?:\.\d+)?\s*" + _UNIT, value, maxsplit=1, flags=re.I)[0]
    value = value.strip(" :-,;\t")
    return value if re.search(r"[A-Za-z]", value) else None


def extract_medication_candidates(ocr: OCRResult, document_id: str) -> list[dict]:
    candidates = []
    for line in (line.strip() for line in ocr.text.splitlines()):
        if not line:
            continue
        strength_match = _STRENGTH.search(line)
        explicit_match = _NAME_LABEL.match(line)
        if not strength_match and not explicit_match:
            continue

        if strength_match:
            prefix = line[:strength_match.start()]
            # If a printed name is after the strength, use the explicitly printed text after it.
            if not _printed_name(prefix) and explicit_match:
                prefix = explicit_match.group(1)
            strength_text = strength_match.group(0)
        else:
            prefix = explicit_match.group(1)
            strength_text = None

        name = _printed_name(prefix)
        if not name:
            continue

        label_match = re.match(
            r"(?i)^\s*(?:\d+[.)]\s*)?(generic\s+name|brand\s+name)\s*[:=\-]", line
        )
        generic = name if label_match and label_match.group(1).lower() == "generic name" else None
        brand = name if label_match and label_match.group(1).lower() == "brand name" else None
        strength, strength_note = normalize_strength(strength_text)
        frequency_match = _FREQUENCY.search(line)
        frequency, frequency_note = normalize_frequency(frequency_match.group(0)) if frequency_match else (None, None)
        dose_match = _DOSE.search(line)
        form_match = _FORM.search(line)
        dosage_form, form_note = normalize_dosage_form(form_match.group(0)) if form_match else (None, None)
        route_match = _ROUTE.search(line)
        route, route_note = normalize_route(route_match.group(0)) if route_match else (None, None)
        start_date_match = re.search(rf"(?i)\bstart\s*date\s*[:=]\s*{_DATE}", line)
        end_date_match = re.search(rf"(?i)\bend\s*date\s*[:=]\s*{_DATE}", line)
        prescriber_match = re.search(r"(?i)\bprescriber\s*[:=]\s*([^,;]+)", line)
        indication_match = re.search(r"(?i)\bindication\s*[:=]\s*([^,;]+)", line)
        duration_match = re.search(r"(?i)\bfor\s+(\d+\s*(?:days?|weeks?|months?))\b", line)
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
            "duration": duration_match.group(1) if duration_match else None,
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
