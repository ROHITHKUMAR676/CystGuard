import json

import httpx

from app.config import Settings
from app.explanation.schemas import ExplanationContent


SYSTEM_PROMPT = """You are the explanation layer for CystGuard, an AI-assisted pancreatic cyst clinical decision-support system.
You do not diagnose disease, calculate risk, reinterpret MRI findings, create Kyoto classifications,
create probabilities, or recommend surgery, medication, treatment, or surveillance intervals.
Explain only structured results already produced by CystGuard deterministic AI, guideline, trust,
and longitudinal services. Use only supplied facts. If information is missing, say unknown or unavailable.
If AI and guideline results disagree, state that clinician review is required. Distinguish AI evidence,
guideline findings, longitudinal changes, and clinician assessment. Never invent a medical finding.
Return only the requested JSON object. Do not add facts or infer a lesion location or diagnosis."""


def explain_with_sarvam(structured_facts: dict, settings: Settings) -> tuple[ExplanationContent, str] | None:
    if not settings.sarvam_api_key:
        return None
    schema = ExplanationContent.model_json_schema()
    payload = {
        "model": settings.sarvam_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(structured_facts, separators=(",", ":"))},
        ],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "cystguard_assessment_explanation", "strict": True, "schema": schema,
        }},
        "temperature": 0.1,
        "max_tokens": 1200,
    }
    try:
        response = httpx.post(
            settings.sarvam_api_url,
            headers={"api-subscription-key": settings.sarvam_api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=settings.sarvam_timeout_seconds,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        parsed = ExplanationContent.model_validate_json(text)
        model = str(response.json().get("model") or settings.sarvam_model)
        return parsed, model
    except Exception:
        return None
