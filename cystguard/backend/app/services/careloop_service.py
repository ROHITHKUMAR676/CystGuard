from app.workflow.models import CareLoopEvent


def record_careloop_event(db, *, patient_id: int, event_type: str, actor_user_id: int | None,
                          source_type: str | None = None, source_id: str | None = None,
                          status: str = "RECORDED", summary: str | None = None) -> CareLoopEvent:
    event = CareLoopEvent(patient_id=patient_id, actor_user_id=actor_user_id,
                          event_type=event_type, source_type=source_type, source_id=source_id,
                          status=status, summary=summary)
    db.add(event)
    return event
