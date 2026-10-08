from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MealContextTag = Literal[
    "HIGH_FAT_OR_FRIED", "VERY_HIGH_FIBER", "VERY_HIGH_SUGAR", "SPICY", "ALCOHOL", "CAFFEINE",
]
NutritionSymptom = Literal[
    "DIARRHEA", "NAUSEA", "VOMITING", "POOR_APPETITE", "EARLY_SATIETY", "CONSTIPATION",
    "ABDOMINAL_PAIN", "DIFFICULTY_SWALLOWING", "TASTE_CHANGE",
]
Appetite = Literal["GOOD", "FAIR", "POOR", "UNKNOWN"]


class NutrientValues(BaseModel):
    calories_kcal: float | None = Field(default=None, ge=0, le=10000)
    carbohydrates_g: float | None = Field(default=None, ge=0, le=1000)
    protein_g: float | None = Field(default=None, ge=0, le=1000)
    fat_g: float | None = Field(default=None, ge=0, le=1000)


class MealConfirmation(BaseModel):
    confirmed: bool
    description: str = Field(min_length=1, max_length=2000)
    food_items: list[str] = Field(default_factory=list, max_length=30)
    food_context_tags: list[MealContextTag] = Field(default_factory=list)
    estimated_portion_grams: float | None = Field(default=None, gt=0, le=10000)
    nutrition: NutrientValues | None = None


class MealPatch(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    food_items: list[str] | None = Field(default=None, max_length=30)
    food_context_tags: list[MealContextTag] | None = None
    estimated_portion_grams: float | None = Field(default=None, gt=0, le=10000)
    nutrition: NutrientValues | None = None


class NutritionProfileUpdate(BaseModel):
    target_daily_kcal: float | None = Field(default=None, gt=0, le=10000)
    target_daily_protein_g: float | None = Field(default=None, gt=0, le=1000)
    documented_pei_pert: bool | None = None
    documented_diabetes: bool | None = None


class NutritionObservationCreate(BaseModel):
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    height_cm: float | None = Field(default=None, gt=0, le=250)
    appetite: Appetite = "UNKNOWN"
    reported_symptoms: list[NutritionSymptom] = Field(default_factory=list)
    intake_interfered: bool = False
    intake_day_complete: bool = False


class MealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: int
    description: str
    patient_confirmed: bool
    recorded_at: datetime
    analysis_status: str
    food_items: list[str] | None = None
    food_context_tags: list[str] | None = None
    nutrition_context_flags: list[dict] | None = None
    raw_provider_output: dict | None = None
    nutrition_estimate: dict | None = None
    patient_corrections: dict | None = None
    final_nutrition: dict | None = None
    estimated_portion_grams: float | None = None
    recognition_confidence: float | None = None
    food_provider: str | None = None
    food_provider_version: str | None = None
    food_model_version: str | None = None
    nutrition_source: str | None = None
    nutrition_source_version: str | None = None
    nutrition_estimation_method: str | None = None
