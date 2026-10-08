import type { MealEntry as Meal } from '../types/meal.js';
import { displayDate, escapeHtml } from '../utils/html.js';
export function NutritionTimeline(meals: Meal[]): string {
  if (!meals.length) return '<div class="empty">No meal entries are stored.</div>';
  return `<div class="timeline">${[...meals].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at)).map((meal) => `<article class="timeline-entry"><span class="timeline-dot"></span><div><small>${escapeHtml(displayDate(meal.recorded_at))}</small><h3>${escapeHtml(meal.description)}</h3><p>${meal.patient_confirmed ? 'Patient confirmed' : 'Patient reported'} · nutrition estimate unavailable</p></div></article>`).join('')}</div>`;
}
