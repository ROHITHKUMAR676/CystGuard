from datetime import date


def calculate_plan_status(target_date: date, as_of: date, terminal_status: str | None = None) -> str:
    if terminal_status in {"COMPLETED", "CANCELLED"}:
        return terminal_status
    if as_of < target_date:
        return "PLANNED"
    if as_of == target_date:
        return "DUE"
    return "OVERDUE"
