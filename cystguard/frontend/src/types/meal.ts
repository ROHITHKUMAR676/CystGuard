export interface NutrientValues {
  calories_kcal?: number | null;
  carbohydrates_g?: number | null;
  protein_g?: number | null;
  fat_g?: number | null;
  estimated_portion_grams?: number | null;
}

export interface MealEntry {
  id: string;
  patient_id: number;
  description: string;
  patient_confirmed: boolean;
  recorded_at: string;
  analysis_status?: string;
  food_items?: string[] | null;
  food_context_tags?: string[] | null;
  nutrition_context_flags?: Array<{ level: string; code: string; message: string; characteristics?: string }> | null;
  raw_provider_output?: Record<string, number> | null;
  nutrition_estimate?: NutrientValues | null;
  patient_corrections?: Record<string, unknown> | null;
  final_nutrition?: NutrientValues | null;
  estimated_portion_grams?: number | null;
  recognition_confidence?: number | null;
  food_provider?: string | null;
  food_provider_version?: string | null;
  food_model_version?: string | null;
  nutrition_source?: string | null;
  nutrition_source_version?: string | null;
  nutrition_estimation_method?: string | null;
}

export interface DailyNutritionEstimate {
  date: string;
  calories_kcal: number;
  protein_g: number;
  carbohydrates_g: number;
  fat_g: number;
  meal_count: number;
  confirmed_count: number;
  day_complete?: boolean;
  percent_of_recorded_target?: number | null;
}

export interface NutritionSummary {
  patient_id: number;
  daily_estimates: DailyNutritionEstimate[];
  average_per_logged_day: Record<string, number> | null;
  average_basis: string;
  recorded_target: { daily_kcal: number | null; daily_protein_g: number | null; source: string | null };
  target_notice: string | null;
  weight: { latest_kg: number | null; latest_recorded_at: string | null; height_cm: number | null; bmi: number | null; history: Array<{ weight_kg: number; date: string }> };
  appetite_history: Array<{ appetite: string; reported_symptoms: string[]; intake_interfered: boolean; date: string }>;
  documented_context: { pei_pert: boolean; diabetes: boolean };
  alerts: Array<{ code: string; level: string; title: string; summary: string; evidence: Record<string, unknown> }>;
  alert_disclaimer: string;
  meals: MealEntry[];
}

export interface FoodAnalysisUnavailable { status: 'UNAVAILABLE'; reason: string }
export interface NutritionUnavailable { status: 'UNAVAILABLE'; reason: string }
