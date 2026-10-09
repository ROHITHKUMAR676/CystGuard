import type { MealEntry, NutritionSummary } from '../../types/meal.js';
import { MealEntry as MealEntryCard } from '../../components/MealEntry.js';
import { displayDate, escapeHtml } from '../../utils/html.js';
import { WeightHistory } from './Meals.js';

function metricBar(label: string, value: number, max: number, unit: string, tone: string): string {
  const width = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return `<div class="nutrition-day-metric"><div><span>${label}</span><b>${Number.isFinite(value) ? `${Math.round(value * 10) / 10} ${unit}` : 'Unavailable'}</b></div><span class="nutrition-day-track" role="img" aria-label="${label}: ${Number.isFinite(value) ? `${value} ${unit}` : 'unavailable'}"><i class="${tone}" style="width:${width}%"></i></span></div>`;
}

function dailyOverview(summary?: NutritionSummary | null): string {
  const days = [...(summary?.daily_estimates || [])]
    .filter((day) => Boolean(day.date))
    .sort((a, b) => b.date.localeCompare(a.date));
  if (!days.length) {
    return '<div class="care-empty"><span class="care-empty-icon" aria-hidden="true">◒</span><b>No daily estimates available</b><p>Estimates appear after meals with nutrition values are recorded. No daily targets are assumed.</p></div>';
  }
  const maximums = {
    calories: Math.max(0, ...days.map((day) => day.calories_kcal)),
    protein: Math.max(0, ...days.map((day) => day.protein_g)),
    carbohydrates: Math.max(0, ...days.map((day) => day.carbohydrates_g)),
    fat: Math.max(0, ...days.map((day) => day.fat_g)),
  };
  return `<label class="nutrition-range-label">Show days<select data-nutrition-range="patient-nutrition"><option value="7">Latest 7 logged days</option><option value="14">Latest 14 logged days</option><option value="all">All logged days</option></select></label><div class="nutrition-days">${days.map((day, index) =>
    `<details class="nutrition-day-card" data-nutrition-day="${index}"${index === 0 ? ' open' : ''}><summary><span><b>${escapeHtml(displayDate(day.date))}</b><small>${day.meal_count} recorded ${day.meal_count === 1 ? 'meal' : 'meals'} · ${day.confirmed_count} confirmed</small></span><span class="pill ${day.day_complete ? 'green' : 'blue'}">${day.day_complete ? 'Marked complete' : 'Partial record'}</span></summary><div class="nutrition-day-content">${metricBar('Energy', day.calories_kcal, maximums.calories, 'kcal', 'bar-energy')}${metricBar('Protein', day.protein_g, maximums.protein, 'g', 'bar-protein')}${metricBar('Carbohydrates', day.carbohydrates_g, maximums.carbohydrates, 'g', 'bar-carbs')}${metricBar('Fat', day.fat_g, maximums.fat, 'g', 'bar-fat')}<p class="muted">Bars compare recorded days with each other; they are not targets or dietary recommendations.</p></div></details>`,
  ).join('')}</div>`;
}

function mealList(meals: MealEntry[]): string {
  if (!meals.length) {
    return '<div class="nutrition-empty-inline"><b>No meal entries recorded</b><span>Use Meals to analyze a photo or save a description.</span></div>';
  }
  return [...meals]
    .sort((a, b) => b.recorded_at.localeCompare(a.recorded_at))
    .slice(0, 5)
    .map((meal) => `<details class="nutrition-recent-meal"><summary><span><b>${escapeHtml(meal.description || 'Meal entry')}</b><small>${escapeHtml(displayDate(meal.recorded_at))}</small></span><span class="pill ${meal.patient_confirmed ? 'green' : 'amber'}">${meal.patient_confirmed ? 'Confirmed' : 'Estimate / unconfirmed'}</span></summary>${MealEntryCard(meal)}</details>`)
    .join('');
}

export function PatientNutrition(props: {
  meals: MealEntry[];
  summary?: NutritionSummary | null;
  observationForm: string;
}): string {
  const summary = props.summary;
  const average = summary?.average_per_logged_day;
  const target = summary?.recorded_target;
  const weight = summary?.weight;
  const alerts = summary?.alerts || [];
  const metrics = `<div class="nutrition-metrics meal-summary-metrics"><div><small>Average energy per logged day</small><b>${average ? `~${Math.round(average.calories_kcal)} kcal` : 'Unavailable'}</b><span>${average ? escapeHtml(summary?.average_basis || 'Based on recorded estimates') : 'No estimate recorded'}</span></div><div><small>Recorded clinician energy target</small><b>${target?.daily_kcal ? `${Math.round(target.daily_kcal)} kcal/day` : 'Not recorded'}</b><span>${target?.source ? `Source: ${escapeHtml(target.source)}` : 'No clinician target supplied'}</span></div><div><small>Latest patient-reported weight</small><b>${weight?.latest_kg ? `${weight.latest_kg} kg` : 'Not recorded'}</b><span>${weight?.latest_recorded_at ? escapeHtml(displayDate(weight.latest_recorded_at)) : 'No weight measurement saved'}</span></div><div><small>Meals recorded</small><b>${props.meals.length}</b><span>${props.meals.filter((meal) => meal.patient_confirmed).length} patient confirmed</span></div></div>`;
  const alertMarkup = alerts.length
    ? `<div class="nutrition-alert-list">${alerts.map((alert) => `<article class="nutrition-alert nutrition-alert-${escapeHtml(alert.level.toLowerCase())}"><b>${escapeHtml(alert.title)}</b><p>${escapeHtml(alert.summary)}</p></article>`).join('')}</div><p class="fine-print">${escapeHtml(summary?.alert_disclaimer || 'Nutrition context is for discussion with your care team.')}</p>`
    : '';
  return `<header class="page-head"><div><p class="eyebrow">NUTRITION OVERVIEW</p><h1>Nutrition</h1><p class="muted">A visual summary of recorded meal estimates and patient-reported context.</p></div><button type="button" class="button primary" data-go="Meals">＋ Log a meal</button></header>
    <section class="nutrition-hero"><div><p class="eyebrow">RECORDED DATA ONLY</p><h2>Your nutrition snapshot</h2><p>Values reflect meals and observations saved to your record. Missing entries remain unavailable.</p></div><span class="nutrition-hero-mark" aria-hidden="true">◒</span></section>
    <section class="card nutrition-summary-card">${metrics}<p class="muted">Logged-day averages do not represent a complete-day intake measure. No dietary target is inferred.</p></section>
    <section class="card nutrition-day-overview"><div class="section-title"><div><p class="eyebrow">RECENT HISTORY</p><h2>Estimated intake by day</h2></div><span class="pill blue">${summary?.daily_estimates.length || 0} logged days</span></div>${dailyOverview(summary)}</section>
    <section class="card nutrition-weight-card"><div class="section-title"><div><p class="eyebrow">PATIENT-REPORTED</p><h2>Weight history</h2></div><span class="pill blue">${weight?.history.length || 0} ${weight?.history.length === 1 ? 'measurement' : 'measurements'}</span></div>${WeightHistory(summary)}</section>
    ${props.observationForm}
    <section class="card nutrition-recent-card"><div class="section-title"><div><p class="eyebrow">MEAL RECORDS</p><h2>Recent meals</h2></div><button type="button" class="text-button" data-go="Meals">Open meal log →</button></div>${mealList(props.meals)}</section>
    ${alertMarkup}
    <p class="fine-print">Nutrition tracking does not diagnose, treat, or reduce pancreatic cyst risk. Estimates and patient-reported context are not medical advice.</p>`;
}
