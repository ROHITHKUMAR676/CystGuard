import re


def normalize_whitespace(value: str) -> str:
    """Normalize spacing only; retain all substantive source text."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def normalize_strength(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    original = value.strip()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(mg|mcg|μg|µg|g|IU|unit(?:s)?)", original, flags=re.IGNORECASE)
    if not match:
        return original, "STRENGTH_NORMALIZATION_UNCERTAIN"
    amount, unit = float(match.group(1)), match.group(2).lower()
    if unit in {"iu", "unit", "units"}:
        unit = "IU" if unit == "iu" else "units"
        shown = str(int(amount)) if amount.is_integer() else str(amount)
        return f"{shown} {unit}", None
    if unit == "g":
        amount *= 1000
        unit = "mg"
    elif unit in {"μg", "µg"}:
        unit = "mcg"
    shown = str(int(amount)) if amount.is_integer() else str(amount)
    return f"{shown} {unit}", None


def normalize_frequency(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    text = re.sub(r"\s+", " ", value.strip().lower())
    replacements = {
        "once daily": "once daily", "once a day": "once daily", "once per day": "once daily", "daily": "once daily",
        "twice daily": "twice daily", "twice a day": "twice daily", "two times a day": "twice daily", "two times day": "twice daily", "bid": "twice daily",
        "three times daily": "three times daily", "three times a day": "three times daily", "tid": "three times daily",
        "four times daily": "four times daily", "four times a day": "four times daily", "qid": "four times daily",
    }
    normalized = replacements.get(text)
    return (normalized, None) if normalized else (value.strip(), "FREQUENCY_NORMALIZATION_UNCERTAIN")


def normalize_dosage_form(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    text = value.strip().lower()
    forms = {"tablet": "tablet", "tablets": "tablet", "tab": "tablet", "tabs": "tablet",
             "capsule": "capsule", "capsules": "capsule", "cap": "capsule", "caps": "capsule",
             "oral solution": "oral solution", "suspension": "suspension", "injection": "injection",
             "inhaler": "inhaler", "cream": "cream", "ointment": "ointment"}
    return (forms[text], None) if text in forms else (value.strip(), "DOSAGE_FORM_NORMALIZATION_UNCERTAIN")


def normalize_route(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    text = re.sub(r"\s+", " ", value.strip().lower())
    routes = {"oral": "oral", "by mouth": "oral", "intravenous": "intravenous", "iv": "intravenous",
              "intramuscular": "intramuscular", "im": "intramuscular", "subcutaneous": "subcutaneous",
              "sc": "subcutaneous", "topical": "topical", "inhaled": "inhaled", "rectal": "rectal"}
    return (routes[text], None) if text in routes else (value.strip(), "ROUTE_NORMALIZATION_UNCERTAIN")
