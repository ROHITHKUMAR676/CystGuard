"""Transparent supportive nutrition context rules; never a diagnosis or treatment plan."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta


DIARRHEA_RELEVANT_TAGS = {
    "HIGH_FAT_OR_FRIED", "VERY_HIGH_FIBER", "VERY_HIGH_SUGAR", "SPICY", "ALCOHOL", "CAFFEINE",
}


def meal_context_flags(
    meal_tags: list[str] | None,
    reported_symptoms: list[str] | None,
    *,
    documented_pei_pert: bool = False,
    documented_diabetes: bool = False,
) -> list[dict[str, str]]:
    """Link explicit patient-entered meal/context tags without implying causality."""
    tags = set(meal_tags or [])
    symptoms = set(reported_symptoms or [])
    flags: list[dict[str, str]] = []
    relevant = sorted(tags & DIARRHEA_RELEVANT_TAGS)
    if "DIARRHEA" in symptoms and relevant:
        flags.append({
            "level": "CONTEXT",
            "code": "DIARRHEA_MEAL_CONTEXT",
            "message": "This meal includes characteristics that may be relevant to your reported diarrhea. This does not show that the meal caused the symptom.",
            "characteristics": ", ".join(relevant),
        })
    if documented_pei_pert and "HIGH_FAT_OR_FRIED" in tags:
        flags.append({
            "level": "CONTEXT",
            "code": "DOCUMENTED_PEI_HIGH_FAT_CONTEXT",
            "message": "A higher-fat meal was recorded alongside documented PEI/PERT context. Review your existing enzyme-use instructions with your care team if needed.",
            "characteristics": "HIGH_FAT_OR_FRIED",
        })
    if documented_diabetes:
        flags.append({
            "level": "CONTEXT",
            "code": "DOCUMENTED_DIABETES_CARBOHYDRATE_CONTEXT",
            "message": "The carbohydrate estimate is available as context for your existing glucose-management plan.",
            "characteristics": "CARBOHYDRATES_DISPLAYED",
        })
    return flags


def _consecutive_runs(day_values: dict[date, float], start: date, end: date):
    run: list[tuple[date, float]] = []
    cursor = start
    while cursor <= end:
        value = day_values.get(cursor)
        if value is None:
            if run:
                yield run
                run = []
        else:
            run.append((cursor, value))
        cursor += timedelta(days=1)
    if run:
        yield run


def nutrition_alerts(
    *,
    daily_totals: dict[date, dict[str, float]],
    complete_days: set[date],
    observations: list[dict],
    meal_contexts: list[dict],
    target_daily_kcal: float | None,
    today: date,
) -> list[dict]:
    """Create triage flags using recorded targets and documented screening thresholds."""
    alerts: list[dict] = []
    if target_daily_kcal and target_daily_kcal > 0:
        calories = {
            day: float(daily_totals.get(day, {}).get("calories_kcal", 0.0))
            for day in complete_days
        }
        # ESPEN 2021: <50% of an individualized requirement for >1 week or
        # 50–75% for >2 weeks merits nutrition intervention assessment.
        for run in _consecutive_runs(calories, today - timedelta(days=20), today):
            if len(run) >= 15 and all(0.50 <= kcal / target_daily_kcal <= 0.75 for _, kcal in run):
                alerts.append({"code": "PERSISTENT_INTAKE_BELOW_RECORDED_TARGET", "level": "REVIEW",
                    "title": "Nutrition review recommended",
                    "summary": "Recorded complete-day estimates have remained between 50% and 75% of the clinician-entered energy target for more than two weeks.",
                    "evidence": {"days": len(run), "target_daily_kcal": target_daily_kcal}})
                break
            if len(run) >= 8 and all(kcal / target_daily_kcal < 0.50 for _, kcal in run):
                alerts.append({"code": "PERSISTENT_INTAKE_BELOW_RECORDED_TARGET", "level": "HIGH_PRIORITY_REVIEW",
                    "title": "Nutrition review recommended",
                    "summary": "Recorded complete-day estimates have remained below 50% of the clinician-entered energy target for more than one week.",
                    "evidence": {"days": len(run), "target_daily_kcal": target_daily_kcal}})
                break

    recent = [item for item in observations if item.get("date") and item["date"] >= today - timedelta(days=7)]
    poor_interference = [item for item in recent if item.get("appetite") == "POOR" and item.get("intake_interfered")]
    if len(poor_interference) >= 3:
        alerts.append({"code": "RECURRENT_POOR_APPETITE", "level": "REVIEW",
            "title": "Nutrition review recommended",
            "summary": "Poor appetite affecting intake was reported repeatedly in the last seven days.",
            "evidence": {"reported_days": len(poor_interference)}})

    contexts_by_symptom: dict[str, set[date]] = defaultdict(set)
    for item in meal_contexts:
        when = item.get("date")
        if when and when >= today - timedelta(days=14):
            for symptom in item.get("symptoms", []):
                if item.get("context_codes"):
                    contexts_by_symptom[symptom].add(when)
    for symptom, days in contexts_by_symptom.items():
        if len(days) >= 2:
            alerts.append({"code": "REPEATED_SYMPTOM_MEAL_CONTEXT", "level": "REVIEW",
                "title": "Nutrition review recommended",
                "summary": f"Meal characteristics and patient-reported {symptom.lower()} were recorded on multiple days. This is an association for review, not a cause.",
                "evidence": {"symptom": symptom, "days": len(days)}})

    weights = sorted((item for item in observations if item.get("weight_kg") and item.get("date")), key=lambda x: x["date"])
    if weights:
        latest = weights[-1]
        for window, threshold in ((30, 0.05), (90, 0.075)):
            baseline = [item for item in weights if (today - timedelta(days=window)) <= item["date"] < latest["date"]]
            if not baseline:
                continue
            first = baseline[0]
            if first["weight_kg"] <= 0:
                continue
            loss = (first["weight_kg"] - latest["weight_kg"]) / first["weight_kg"]
            if loss >= threshold:
                high = loss > threshold
                alerts.append({"code": "RECENT_WEIGHT_DECLINE", "level": "HIGH_PRIORITY_REVIEW" if high else "REVIEW",
                    "title": "Nutrition review recommended",
                    "summary": f"Recorded weight declined by {loss * 100:.1f}% over the available {window}-day comparison. Weight change needs clinical context and is not a diagnosis.",
                    "evidence": {"weight_loss_percent": round(loss * 100, 1), "window_days": window}})
                break
    return alerts
