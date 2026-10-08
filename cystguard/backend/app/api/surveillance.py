from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.access import require_patient_access, require_patient_doctor
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from app.schemas.surveillance import EventCreate, SurveillanceCreate, SurveillanceRead
from app.services.surveillance_service import calculate_plan_status
from app.services.audit_service import record_audit_event
from app.services.careloop_service import record_careloop_event
from app.surveillance.models import SurveillanceEvent, SurveillancePlan

router = APIRouter(prefix="/patients", tags=["Surveillance"])
Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]


@router.get("/{patient_id}/surveillance")
def list_plans(patient_id: int, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    plans = db.scalars(select(SurveillancePlan).where(SurveillancePlan.patient_user_id == patient_id).order_by(SurveillancePlan.created_at)).all()
    return [dict(SurveillanceRead.model_validate(p).model_dump(), status=calculate_plan_status(p.target_follow_up_date, date.today(), p.status)) for p in plans]


@router.post("/{patient_id}/surveillance", status_code=201)
def create_plan(patient_id: int, payload: SurveillanceCreate, db: Db, user: Current):
    require_patient_doctor(db, user, patient_id)
    plan = SurveillancePlan(patient_user_id=patient_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return dict(SurveillanceRead.model_validate(plan).model_dump(),
                status=calculate_plan_status(plan.target_follow_up_date, date.today(), plan.status))


@router.get("/{patient_id}/surveillance/{plan_id}")
def read_plan(patient_id: int, plan_id: str, db: Db, user: Current):
    require_patient_access(db, user, patient_id)
    plan = db.scalar(select(SurveillancePlan).where(SurveillancePlan.id == plan_id, SurveillancePlan.patient_user_id == patient_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Surveillance plan not found")
    events = db.scalars(select(SurveillanceEvent).where(SurveillanceEvent.plan_id == plan_id)).all()
    return {"plan": dict(SurveillanceRead.model_validate(plan).model_dump(), status=calculate_plan_status(plan.target_follow_up_date, date.today(), plan.status)),
            "events": [{"id": e.id, "plan_id": e.plan_id, "created_by_user_id": e.created_by_user_id,
                        "event_type": e.event_type, "planned_date": e.planned_date,
                        "completed_at": e.completed_at, "status": calculate_plan_status(e.planned_date, date.today(), e.status),
                        "notes": e.notes, "reviewed_by_user_id": e.reviewed_by_user_id} for e in events]}


@router.post("/{patient_id}/surveillance/{plan_id}/complete")
def complete_plan(patient_id: int, plan_id: str, db: Db, user: Current):
    require_patient_doctor(db, user, patient_id)
    plan = db.scalar(select(SurveillancePlan).where(SurveillancePlan.id == plan_id, SurveillancePlan.patient_user_id == patient_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Surveillance plan not found")
    plan.status = "COMPLETED"
    plan.last_reviewed_at = datetime.now(timezone.utc)
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id,
                          event_type="SURVEILLANCE_COMPLETED", source_type="SURVEILLANCE_PLAN",
                          source_id=plan.id, summary="Clinician recorded surveillance plan completion")
    record_audit_event(db, actor_user_id=user.id, action="SURVEILLANCE_PLAN_COMPLETED",
                       resource_type="SURVEILLANCE_PLAN", resource_id=plan.id)
    db.commit()
    return {"id": plan.id, "status": plan.status, "last_reviewed_at": plan.last_reviewed_at}


@router.post("/{patient_id}/surveillance/{plan_id}/events", status_code=201)
def create_event(patient_id: int, plan_id: str, payload: EventCreate, db: Db, user: Current):
    require_patient_doctor(db, user, patient_id)
    plan = db.scalar(select(SurveillancePlan).where(SurveillancePlan.id == plan_id, SurveillancePlan.patient_user_id == patient_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Surveillance plan not found")
    event = SurveillanceEvent(plan_id=plan.id, created_by_user_id=user.id, event_type=payload.event_type,
                              planned_date=payload.planned_date, notes=payload.notes)
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"id": event.id, "plan_id": event.plan_id, "event_type": event.event_type,
            "planned_date": event.planned_date,
            "status": calculate_plan_status(event.planned_date, date.today(), event.status), "notes": event.notes}


@router.post("/{patient_id}/surveillance/{plan_id}/events/{event_id}/complete")
def complete_event(patient_id: int, plan_id: str, event_id: str, db: Db, user: Current):
    require_patient_doctor(db, user, patient_id)
    event = db.scalar(select(SurveillanceEvent).join(SurveillancePlan).where(
        SurveillanceEvent.id == event_id, SurveillanceEvent.plan_id == plan_id,
        SurveillancePlan.patient_user_id == patient_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Follow-up event not found")
    event.status, event.completed_at, event.reviewed_by_user_id = "COMPLETED", datetime.now(timezone.utc), user.id
    record_careloop_event(db, patient_id=patient_id, actor_user_id=user.id,
                          event_type="SURVEILLANCE_COMPLETED", source_type="SURVEILLANCE_EVENT",
                          source_id=event.id, summary="Clinician recorded follow-up event completion")
    record_audit_event(db, actor_user_id=user.id, action="SURVEILLANCE_EVENT_COMPLETED",
                       resource_type="SURVEILLANCE_EVENT", resource_id=event.id)
    db.commit()
    return {"id": event.id, "status": event.status, "completed_at": event.completed_at}
