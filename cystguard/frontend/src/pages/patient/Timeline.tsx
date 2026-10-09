import type { MealEntry } from '../../types/meal.js';
import type {
  MedicationRecord,
  MRIStudySummary,
  SurveillancePlan,
  Symptom,
} from '../../types/patient.js';
import { displayDate, escapeHtml } from '../../utils/html.js';

interface CareEvent {
  event_id?: string;
  event_type?: string;
  source_type?: string | null;
  source_id?: string | null;
  summary?: string | null;
  occurred_at?: string;
  status?: string;
}

interface ClinicalNote {
  id: string;
  body: string;
  created_at: string;
  source_context?: string;
}

interface TimelineEntry {
  id: string;
  date: string;
  category: string;
  icon: string;
  title: string;
  status: string;
  description: string;
  details?: string;
}

interface Props {
  studies: MRIStudySummary[];
  orderingComplete?: boolean;
  events: CareEvent[];
  symptoms: Symptom[];
  notes: ClinicalNote[];
  medications: MedicationRecord[];
  surveillance: SurveillancePlan[];
  meals: MealEntry[];
}

function medicationName(record: MedicationRecord): string {
  const fields = record.verified_fields || record.extracted_fields;
  const field = fields.name;
  if (field && typeof field === 'object' && 'value' in field) {
    const medicationField = field as { normalized_value?: unknown; value?: unknown };
    return String(medicationField.normalized_value ?? medicationField.value ?? 'Medication details not recorded');
  }
  return String(field || 'Medication details not recorded');
}

function eventCategory(event: CareEvent): string {
  const type = `${event.event_type || ''} ${event.source_type || ''}`.toUpperCase();
  if (type.includes('MRI') || type.includes('STUDY')) return 'mri';
  if (type.includes('SURVEILLANCE') || type.includes('FOLLOW_UP')) return 'surveillance';
  if (type.includes('MEAL') || type.includes('NUTRITION')) return 'nutrition';
  if (type.includes('MEDICATION')) return 'medication';
  if (type.includes('SYMPTOM')) return 'symptoms';
  return 'review';
}

function categoryName(category: string): string {
  return ({
    mri: 'MRI',
    review: 'Care review',
    symptoms: 'Symptoms',
    medication: 'Medication',
    nutrition: 'Nutrition',
    surveillance: 'Surveillance',
  } as Record<string, string>)[category] || 'Care update';
}

function hasSource(entries: TimelineEntry[], category: string, id: string): boolean {
  return entries.some((entry) => entry.category === category && entry.id === id);
}

function buildEntries(props: Props): TimelineEntry[] {
  const entries: TimelineEntry[] = [];

  for (const study of props.studies) {
    const result = study.assessments?.[0];
    const measurements = (study.measurements || []).map((measurement) => {
      const feature = escapeHtml(String(measurement.feature || 'Measurement'));
      const value = measurement.value == null
        ? escapeHtml(String(measurement.finding_status || 'Unknown'))
        : `${escapeHtml(String(measurement.value))} ${escapeHtml(String(measurement.unit || ''))}`;
      const source = escapeHtml(String(measurement.source || 'Source not recorded'));
      return `<li><b>${feature}</b><span>${value}</span><small>${source}</small></li>`;
    }).join('');
    const score = typeof result?.raw_score === 'number' && Number.isFinite(result.raw_score)
      ? `Recorded model score ${result.raw_score.toFixed(3)} · not a probability.`
      : 'No model score recorded.';
    const profile = result?.risk_class === 'HIGH_RISK'
      ? 'Higher risk profile recorded'
      : result?.risk_class === 'NO_LOW_RISK'
        ? 'No / low risk profile recorded'
        : 'Assessment not available';
    entries.push({
      id: study.id,
      date: study.study_date || study.uploaded_at,
      category: 'mri',
      icon: 'M',
      title: 'MRI study',
      status: result ? profile : 'Study stored · no assessment recorded',
      description: `${study.study_date ? 'Study date' : 'Upload date'} · ${score}`,
      details: `<p>${escapeHtml(profile)}</p>${measurements ? `<h4>Sourced measurements</h4><ul class="timeline-measurements">${measurements}</ul>` : '<p>No sourced measurements are recorded for this study.</p>'}`,
    });
  }

  for (const symptom of props.symptoms) {
    const severity = symptom.severity == null ? 'Severity not recorded' : `Patient-reported severity ${symptom.severity}/10`;
    entries.push({
      id: symptom.id,
      date: symptom.onset_date || symptom.recorded_at,
      category: 'symptoms',
      icon: '+',
      title: symptom.symptom_type || 'Symptom entry',
      status: symptom.review_status?.replace(/_/g, ' ') || 'Patient reported',
      description: `${severity}${symptom.duration ? ` · ${symptom.duration}` : ''}`,
      details: `<p>${escapeHtml(symptom.notes || 'No additional note recorded.')}</p><p>Recorded ${escapeHtml(displayDate(symptom.recorded_at))}. Review status: ${escapeHtml(symptom.review_status || 'Not recorded')}.</p>`,
    });
  }

  for (const note of props.notes) {
    entries.push({
      id: note.id,
      date: note.created_at,
      category: 'review',
      icon: 'N',
      title: note.source_context?.replace(/_/g, ' ') || 'Care note',
      status: 'Saved note',
      description: note.body,
      details: `<p>${escapeHtml(note.body)}</p>`,
    });
  }

  for (const medication of props.medications) {
    entries.push({
      id: medication.id,
      date: medication.verified_at || medication.created_at,
      category: 'medication',
      icon: 'Rx',
      title: medicationName(medication),
      status: medication.verification_status === 'VERIFIED' ? 'Clinician verified' : 'Unverified record',
      description: `Medication status: ${medication.medication_status.replace(/_/g, ' ').toLowerCase()}.`,
      details: `<p>Verification: ${escapeHtml(medication.verification_status)} · Medication status: ${escapeHtml(medication.medication_status)}.</p><p>Source document: ${escapeHtml(medication.source_document_id || 'Not recorded')}</p>`,
    });
  }

  for (const plan of props.surveillance) {
    const completed = plan.status.toUpperCase() === 'COMPLETED';
    entries.push({
      id: plan.id,
      date: plan.target_follow_up_date,
      category: 'surveillance',
      icon: '↗',
      title: plan.reason || 'Scheduled follow-up',
      status: completed ? 'Completed' : plan.status.replace(/_/g, ' '),
      description: completed ? 'Recorded follow-up date' : 'Planned follow-up date',
      details: `<p>${escapeHtml(plan.notes || 'No additional plan details recorded.')}</p>${plan.created_at ? `<p>Plan recorded ${escapeHtml(displayDate(plan.created_at))}.</p>` : ''}`,
    });
  }

  for (const meal of props.meals) {
    const nutrition = meal.final_nutrition || meal.nutrition_estimate;
    const estimates = nutrition
      ? `Calories ${nutrition.calories_kcal == null ? 'not recorded' : `${Math.round(nutrition.calories_kcal)} kcal`} · Protein ${nutrition.protein_g == null ? 'not recorded' : `${nutrition.protein_g} g`}`
      : 'Nutrition estimate unavailable';
    entries.push({
      id: meal.id,
      date: meal.recorded_at,
      category: 'nutrition',
      icon: 'N',
      title: meal.description || 'Meal entry',
      status: meal.patient_confirmed ? 'Patient confirmed' : 'Not confirmed',
      description: estimates,
      details: `<p>${escapeHtml(estimates)}</p><p>${meal.patient_confirmed ? 'Values are patient-confirmed.' : 'Values remain estimates until reviewed and confirmed.'}</p>`,
    });
  }

  for (const event of props.events) {
    const category = eventCategory(event);
    const sourceId = String(event.source_id || '');
    if (sourceId && hasSource(entries, category, sourceId)) continue;
    const eventType = String(event.event_type || 'Care update');
    entries.push({
      id: event.event_id || `${eventType}:${event.occurred_at || entries.length}`,
      date: event.occurred_at || '',
      category,
      icon: category === 'mri' ? 'M' : category === 'symptoms' ? '+' : category === 'medication' ? 'Rx' : category === 'surveillance' ? '↗' : category === 'nutrition' ? 'N' : '•',
      title: eventType.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (letter: string) => letter.toUpperCase()),
      status: String(event.status || 'RECORDED').replace(/_/g, ' '),
      description: event.summary || 'A care update was recorded.',
    });
  }

  return entries.sort((a, b) => {
    const aTime = new Date(a.date).getTime();
    const bTime = new Date(b.date).getTime();
    return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0);
  });
}

export function PatientTimeline(props: Props): string {
  const entries = buildEntries(props);
  const categories = [...new Set(entries.map((entry) => entry.category))];
  const filters = ['all', ...categories];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const timeline = entries.length
    ? `<div class="feed-filters" data-feed-controls="timeline" aria-label="Filter health timeline">${filters.map((filter) =>
      `<button class="feed-filter ${filter === 'all' ? 'active' : ''}" type="button" data-feed-filter="${filter}" data-feed-name="timeline" aria-pressed="${filter === 'all'}">${filter === 'all' ? 'All records' : categoryName(filter)}</button>`,
    ).join('')}</div><div class="health-timeline">${entries.map((entry) => {
      const timestamp = new Date(entry.date).getTime();
      const isFuture = Number.isFinite(timestamp) && timestamp >= today.getTime()
        && entry.category === 'surveillance'
        && !entry.status.toUpperCase().includes('COMPLETED');
      const dateGroup = Number.isFinite(timestamp)
        ? new Date(entry.date).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
        : 'Date not recorded';
      return `<article class="health-timeline-item ${isFuture ? 'is-upcoming' : ''}" data-feed-item="timeline" data-feed-category="${entry.category}"><span class="health-timeline-icon health-icon-${entry.category}" aria-hidden="true">${entry.icon}</span><div class="health-timeline-card"><div class="health-timeline-meta"><span>${escapeHtml(categoryName(entry.category))} · ${escapeHtml(dateGroup)}</span><time>${escapeHtml(displayDate(entry.date))}</time></div><div class="health-timeline-title"><h3>${escapeHtml(entry.title)}</h3><span class="pill ${isFuture ? 'blue' : entry.status.toUpperCase().includes('VERIFIED') || entry.status.toUpperCase().includes('COMPLETED') ? 'green' : 'amber'}">${isFuture ? 'Upcoming' : escapeHtml(entry.status)}</span></div><p>${escapeHtml(entry.description)}</p>${entry.details ? `<details class="timeline-details"><summary>View record details</summary>${entry.details}</details>` : ''}</div></article>`;
    }).join('')}</div>`
    : '<div class="care-empty"><span class="care-empty-icon" aria-hidden="true">↗</span><b>No timeline records yet</b><p>Saved studies and other dated records will appear here when available.</p></div>';

  return `<header class="page-head"><div><p class="eyebrow">YOUR HEALTH HISTORY</p><h1>Timeline</h1><p class="muted">Dated records from your care, with their original review and confirmation status.</p></div></header>${!props.orderingComplete ? '<p class="timeline-notice">Some study dates are missing; available upload dates are used when present.</p>' : ''}<section class="card timeline-shell"><div class="section-title"><div><p class="eyebrow">CHRONOLOGICAL RECORD</p><h2>Health timeline</h2></div><span class="pill blue">${entries.length} ${entries.length === 1 ? 'record' : 'records'}</span></div>${timeline}<p class="care-disclaimer">Patient-reported, extracted, estimated, and clinician-reviewed records are labelled separately. Missing information is not inferred.</p></section>`;
}
