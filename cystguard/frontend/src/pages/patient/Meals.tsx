import type { MealEntry, NutritionSummary } from '../../types/meal.js';
import { MealAnalyzer } from '../../components/MealAnalyzer.js';
import { MealEntry as MealEntryCard } from '../../components/MealEntry.js';
import { displayDate, escapeHtml } from '../../utils/html.js';
import type { UploadFlowState } from '../../components/UploadProgress.js';

export function WeightHistory(summary?: NutritionSummary | null): string {
  const history = [...(summary?.weight.history || [])]
    .filter((entry) => Number.isFinite(entry.weight_kg) && entry.weight_kg > 0)
    .sort((a, b) => a.date.localeCompare(b.date));
  if (!history.length) {
    return '<div class="nutrition-empty-inline"><b>No weight history recorded</b><span>Weight will appear here only after it has been recorded.</span></div>';
  }
  if (history.length === 1) {
    return `<div class="weight-single"><b>${history[0].weight_kg} kg</b><span>One patient-reported measurement · ${escapeHtml(displayDate(history[0].date))}</span></div>`;
  }
  const width = Math.max(440, history.length * 108);
  const left = 42;
  const right = width - 24;
  const values = history.map((entry) => entry.weight_kg);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = history.map((entry, index) => {
    const x = history.length === 1 ? width / 2 : left + index * ((right - left) / (history.length - 1));
    const y = 118 - ((entry.weight_kg - min) / range) * 72;
    return { ...entry, x, y };
  });
  const line = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
  return `<div class="weight-chart-scroll"><svg class="weight-chart" viewBox="0 0 ${width} 178" role="img" aria-label="Patient-reported weight history in kilograms">${[0, .5, 1].map((fraction) => `<line x1="${left}" y1="${46 + fraction * 72}" x2="${right}" y2="${46 + fraction * 72}" class="nutrition-gridline"/>`).join('')}<path d="${line}" class="weight-chart-line"/>${points.map((point) => `<g><circle cx="${point.x}" cy="${point.y}" r="5" class="weight-chart-point"/><text x="${point.x}" y="${point.y - 10}" text-anchor="middle" class="weight-chart-value">${point.weight_kg} kg</text><text x="${point.x}" y="151" text-anchor="middle" class="weight-chart-date">${escapeHtml(displayDate(point.date))}</text></g>`).join('')}</svg></div><p class="muted">Patient-reported measurements · no target or trend interpretation is applied.</p>`;
}

function dailyMeals(meals: MealEntry[]): string {
  const groups = new Map<string, MealEntry[]>();
  for (const meal of [...meals].sort((a, b) => b.recorded_at.localeCompare(a.recorded_at))) {
    const day = meal.recorded_at?.slice(0, 10) || 'date-unavailable';
    groups.set(day, [...(groups.get(day) || []), meal]);
  }
  if (!groups.size) {
    return '<div class="care-empty"><span class="care-empty-icon" aria-hidden="true">◒</span><b>Your meal log is ready</b><p>Analyze a meal photo or save a description to start building your own history.</p></div>';
  }
  return `<label class="meal-date-filter">Filter by recorded date<input type="date" data-meal-date-filter="meal-history" aria-label="Filter meals by date"></label><div class="meal-days">${[...groups.entries()].map(([day, items], index) =>
    `<details class="meal-day"${index === 0 ? ' open' : ''} data-meal-day="${escapeHtml(day)}"><summary><span><b>${day === 'date-unavailable' ? 'Date not recorded' : escapeHtml(displayDate(day))}</b><small>${items.length} ${items.length === 1 ? 'meal' : 'meals'} recorded</small></span><span class="meal-day-count">${items.filter((meal) => meal.patient_confirmed).length} confirmed</span></summary><div class="meal-day-entries">${items.map((meal) => MealEntryCard(meal)).join('')}</div></details>`,
  ).join('')}</div>`;
}

export function PatientMeals(props: { meals: MealEntry[]; summary?: NutritionSummary | null; uploadFlow?: UploadFlowState | null; latestMeal?: MealEntry | null }): string {
  const alerts = props.summary?.alerts || [];
  const alertMarkup = alerts.map((alert) => `<div class="nutrition-alert nutrition-alert-${escapeHtml(alert.level.toLowerCase())}"><b>${escapeHtml(alert.title)}</b><p>${escapeHtml(alert.summary)}</p></div>`).join('');
  const loggedAverage = props.summary?.average_per_logged_day;
  const target = props.summary?.recorded_target;
  const confirmedCount = props.meals.filter((meal) => meal.patient_confirmed).length;
  const metrics = `<div class="nutrition-metrics meal-summary-metrics"><div><small>Meals recorded</small><b>${props.meals.length}</b><span>${confirmedCount} patient confirmed</span></div><div><small>Logged-day average energy</small><b>${loggedAverage ? `~${Math.round(loggedAverage.calories_kcal)} kcal` : 'Unavailable'}</b><span>${loggedAverage ? escapeHtml(props.summary?.average_basis || 'Based on saved records') : 'No estimate recorded'}</span></div><div><small>Clinician-recorded energy target</small><b>${target?.daily_kcal ? `${Math.round(target.daily_kcal)} kcal/day` : 'Not recorded'}</b><span>${target?.source ? `Source: ${escapeHtml(target.source)}` : 'No target supplied'}</span></div><div><small>Latest recorded weight</small><b>${props.summary?.weight.latest_kg ? `${props.summary.weight.latest_kg} kg` : 'Not recorded'}</b><span>${props.summary?.weight.latest_recorded_at ? escapeHtml(displayDate(props.summary.weight.latest_recorded_at)) : 'No weight entry'}</span></div></div>`;
  return `<header class="page-head"><div><p class="eyebrow">MEAL LOGGING</p><h1>Meals</h1><p class="muted">Keep a visual record of meals and review estimates before confirming them.</p></div><a class="button primary meal-log-jump" href="#meal-log">＋ Log a meal</a></header>
    <section class="card meal-overview"><div class="section-title"><div><p class="eyebrow">YOUR NUTRITION RECORD</p><h2>At a glance</h2></div><span class="pill blue">${confirmedCount} confirmed</span></div>${metrics}<p class="muted">Estimates reflect recorded meals only. They do not represent complete daily intake or dietary requirements.</p></section>
    ${alertMarkup ? `<section class="nutrition-alert-list" aria-label="Nutrition context">${alertMarkup}</section>` : ''}
    <section class="meal-log-anchor" id="meal-log">${MealAnalyzer(props.uploadFlow)}</section>
    ${props.latestMeal ? `<section class="card upload-result meal-latest"><div class="section-title"><div><p class="eyebrow">READY FOR YOUR REVIEW</p><h2>Latest meal estimate</h2></div><span class="pill amber">Not confirmed</span></div>${MealEntryCard(props.latestMeal)}</section>` : ''}
    <section class="card meal-description-card"><div class="section-title"><div><p class="eyebrow">QUICK ENTRY</p><h2>Log without a photo</h2></div><span class="meal-step">01</span></div><p class="muted">Save a description now; nutrition values remain unavailable unless an estimate is recorded separately.</p><form id="meal-form" class="meal-description-form"><label>Meal description<input name="name" required maxlength="2000" placeholder="What did you have?"></label><label class="meal-confirm-check"><input name="confirm" type="checkbox"> I confirm this description</label><button class="button" type="submit">Save meal description</button></form></section>
    <section class="card meal-history"><div class="section-title"><div><p class="eyebrow">PERSONAL RECORD</p><h2>Meal history</h2></div><span class="pill blue">${props.meals.length} ${props.meals.length === 1 ? 'entry' : 'entries'}</span></div>${dailyMeals(props.meals)}</section>
    <section class="card weight-history"><div class="section-title"><div><p class="eyebrow">PATIENT-REPORTED</p><h2>Weight history</h2></div><span class="pill blue">${props.summary?.weight.history.length || 0} ${props.summary?.weight.history.length === 1 ? 'measurement' : 'measurements'}</span></div>${WeightHistory(props.summary)}</section>
    <p class="fine-print">Nutrition information is for record keeping and does not diagnose, treat, or reduce pancreatic cyst risk. Discuss nutrition concerns with your care team.</p>`;
}
