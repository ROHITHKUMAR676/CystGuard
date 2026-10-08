import re

from app.ocr.normalizer import normalize_whitespace
from app.ocr.provider import OCRResult
from app.schemas.report import DocumentType, ExtractedField, FieldProvenance, FieldStatus


def _source(ocr: OCRResult, document_id: str, snippet: str | None) -> FieldProvenance | None:
    if not snippet:
        return None
    page = next((p for p in ocr.pages if snippet in p.text), None)
    return FieldProvenance(
        source_document_id=document_id, source_type=DocumentType.REPORT,
        page=page.page_number if page else None, source_text=snippet,
        extraction_method=ocr.method,
        extraction_confidence=page.extraction_confidence if page else None,
    )


def _candidate(ocr: OCRResult, document_id: str, value: str | float | None, snippet: str | None, normalized=None, notes=()) -> dict:
    source = _source(ocr, document_id, snippet)
    return ExtractedField(
        value=value, normalized_value=normalized if normalized is not None else value,
        status=FieldStatus.PRESENT if value is not None else FieldStatus.UNKNOWN,
        extraction_confidence=source.extraction_confidence if source else None,
        provenance=source, needs_verification=True, normalization_notes=tuple(notes),
    ).model_dump(mode="json")


def _label(text: str, labels: str) -> tuple[str | None, str | None]:
    match = re.search(rf"(?im)^\s*(?:{labels})\s*[:\-]\s*(.+?)\s*$", text)
    return (match.group(1).strip(), match.group(0).strip()) if match else (None, None)


def _section(text: str, label: str) -> tuple[str | None, str | None]:
    match = re.search(rf"(?ims)^\s*{label}\s*[:\-]\s*(.+?)(?=^\s*(?:impression|findings|recommendation|conclusion)\s*[:\-]|\Z)", text)
    if not match:
        return None, None
    value = normalize_whitespace(match.group(1))
    return (value, match.group(0).strip()) if value else (None, None)


def extract_report_fields(ocr: OCRResult, document_id: str) -> dict[str, dict]:
    text = ocr.text
    fields: dict[str, tuple[str | float | None, str | None, object | None, tuple[str, ...]]] = {}
    labels = {
        "report_type": r"report\s*type|document\s*type",
        "patient_name": r"patient\s*name|name",
        "patient_identifier": r"patient\s*(?:id|identifier|mrn)|mrn|medical\s*record\s*(?:number|no\.? )",
        "report_date": r"report\s*date|issued\s*date|date\s*of\s*report",
        "study_date": r"study\s*date|examination\s*date|procedure\s*date",
    }
    for key, pattern in labels.items():
        value, source = _label(text, pattern)
        fields[key] = (value, source, value, ())

    modality_match = re.search(r"\b(MRI|MR|CT|ultrasound|US|PET(?:/CT)?)\b", text, re.I)
    fields["modality"] = (modality_match.group(1) if modality_match else None, modality_match.group(0) if modality_match else None, None, ())
    body_match = re.search(r"\b(pancreas|pancreatic)\b", text, re.I)
    fields["body_region"] = ("pancreas" if body_match else None, body_match.group(0) if body_match else None, None, ())
    for key, label in (("findings", "findings"), ("impression", "impression")):
        value, source = _section(text, label)
        fields[key] = (value, source, value, ())

    cyst = re.search(r"(?i)\b(?:cyst(?:ic)?\s+(?:lesion|structure|measur(?:ing|es|ed))|IPMN)[^\n]{0,100}?\b(\d+(?:\.\d+)?)\s*(mm|cm)\b", text)
    if cyst:
        amount = float(cyst.group(1)) * (10 if cyst.group(2).lower() == "cm" else 1)
        source_size = f"{cyst.group(1)} {cyst.group(2).lower()}"
        normalized_size = f"{int(amount) if amount.is_integer() else amount} mm"
        fields["cyst_size_mm"] = (source_size, cyst.group(0), normalized_size, ())
    else:
        fields["cyst_size_mm"] = (None, None, None, ())
    location = re.search(r"(?i)(?:cyst|lesion|IPMN)[^\n]{0,100}\b(?:pancreatic\s+)?(head|body|tail|uncinate)\b|\b(head|body|tail|uncinate)\s+of\s+(?:the\s+)?pancreas", text)
    loc = next((g for g in location.groups() if g), None) if location else None
    fields["cyst_location"] = (loc.upper() if loc else None, location.group(0) if location else None, loc.upper() if loc else None, ())
    mpd = re.search(r"(?i)\b(?:MPD|main\s+pancreatic\s+duct)\b[^\n]{0,50}?\b(\d+(?:\.\d+)?)\s*(mm|cm)\b", text)
    if mpd:
        value = float(mpd.group(1)) * (10 if mpd.group(2).lower() == "cm" else 1)
        source_measurement = f"{mpd.group(1)} {mpd.group(2).lower()}"
        normalized_measurement = f"{int(value) if value.is_integer() else value} mm"
        fields["mpd_mm"] = (source_measurement, mpd.group(0), normalized_measurement, ())
    else:
        fields["mpd_mm"] = (None, None, None, ())

    line_patterns = {
        "mural_nodule_mention": r"(?im)^.*mural\s+nodule.*$",
        "solid_component_mention": r"(?im)^.*solid\s+component.*$",
        "cyst_wall_characteristics": r"(?im)^.*(?:cyst\s+wall|wall\s+(?:thickening|enhancement)).*$",
        "ductal_findings": r"(?im)^.*(?:duct|ductal|MPD|main pancreatic duct).*$",
    }
    for key, pattern in line_patterns.items():
        match = re.search(pattern, text)
        fields[key] = (match.group(0).strip() if match else None, match.group(0).strip() if match else None, None, ())
    fields["other_findings"] = (None, None, None, ())
    return {key: _candidate(ocr, document_id, *values) for key, values in fields.items()}
