from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Symptom(Base):
    __tablename__ = "symptoms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    symptom_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="PATIENT_REPORTED")
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING_REVIEW")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    author_role: Mapped[str] = mapped_column(String(16), nullable=False)
    visibility: Mapped[str] = mapped_column(String(24), nullable=False)
    source_context: Mapped[str] = mapped_column(String(64), nullable=False, default="CARE_WORKFLOW")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CareLoopEvent(Base):
    __tablename__ = "careloop_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RECORDED")
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ReviewItem(Base):
    __tablename__ = "review_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_type: Mapped[str] = mapped_column(String(48), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="NORMAL")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    source_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class MealEntry(Base):
    __tablename__ = "meal_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    patient_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(24), nullable=False, default="DESCRIPTION_ONLY", server_default="DESCRIPTION_ONLY")
    food_image_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    food_image_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    food_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    food_context_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    nutrition_context_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw_provider_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    nutrition_estimate: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    patient_corrections: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_nutrition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estimated_portion_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    recognition_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    food_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    food_provider_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    food_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nutrition_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nutrition_source_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nutrition_estimation_method: Mapped[str | None] = mapped_column(String(128), nullable=True)


class NutritionProfile(Base):
    __tablename__ = "nutrition_profiles"
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    target_daily_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_daily_protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    documented_pei_pert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    documented_diabetes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class NutritionObservation(Base):
    __tablename__ = "nutrition_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    recorded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    appetite: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    reported_symptoms: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    intake_interfered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    intake_day_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class CareMessage(Base):
    __tablename__ = "care_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
