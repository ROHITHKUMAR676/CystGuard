from app.ocr.medication_ocr_service import normalized_medication_key


def verify_report_fields(extracted: dict, corrections: dict) -> dict:
    """Keep extracted values immutable and return the clinician-confirmed overlay."""
    verified = dict(extracted)
    verified.update(corrections)
    return verified


def verify_medication_fields(extracted: dict, corrections: dict) -> dict:
    verified = dict(extracted)
    verified.update(corrections)
    return verified


def find_medication_conflicts(records: list[dict]) -> list[dict]:
    conflicts = []
    fields = ("strength", "normalized_strength", "dose", "dosage_form", "frequency", "normalized_frequency", "route", "normalized_route")
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if normalized_medication_key(left) != normalized_medication_key(right):
                continue
            differing = {}
            for field in fields:
                a, b = left.get(field), right.get(field)
                if a is not None and b is not None and str(a).strip().lower() != str(b).strip().lower():
                    differing[field] = (a, b)
            if differing:
                conflicts.append({"left": left, "right": right, "conflicting_fields": differing})
    return conflicts
