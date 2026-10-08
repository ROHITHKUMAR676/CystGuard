from sqlalchemy.orm import Session

from app.audit.models import AuditEvent


def record_audit_event(
    db: Session,
    *,
    actor_user_id: int,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict | None = None,
) -> AuditEvent:
    """Persist a minimal audit event; do not copy document text or clinical values."""
    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event
