import type { MealEntry } from '../../types/meal.js';
import type { MedicationRecord, SurveillancePlan, Symptom } from '../../types/patient.js';
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

interface CareNote {
  id: string;
  body: string;
  created_at: string;
}

interface Props {
  events: CareEvent[];
  symptoms: Symptom[];
  medications: MedicationRecord[];
  surveillance: SurveillancePlan[];
  meals: MealEntry[];
  notes: CareNote[];
  hasAssessment: boolean;
}

function category(event: CareEvent): string {
  const type = String(event.event_type || '').toUpperCase();
  if (type.includes('MRI')) return 'mri';
  if (type.includes('SURVEILLANCE') || type.includes('FOLLOW_UP')) return 'surveillance';
  if (type.includes('MEAL') || type.includes('NUTRITION')) return 'nutrition';
  if (type.includes('MEDICATION')) return 'medication';
  if (type.includes('SYMPTOM')) return 'symptoms';
  return 'review';
}

function categoryLabel(value: string): string {
  return ({
    mri: 'Imaging',
    review: 'Care review',
    symptoms: 'Symptoms',
    medication: 'Medication',
    nutrition: 'Nutrition',
    surveillance: 'Surveillance',
  } as Record<string, string>)[value] || 'Care update';
}

function medicationName(record: MedicationRecord): string {
  const fields = record.verified_fields || record.extracted_fields;
  const raw = fields.name;
  if (raw && typeof raw === 'object' && 'value' in raw) {
    const field = raw as { normalized_value?: unknown; value?: unknown };
    return String(field.normalized_value ?? field.value ?? 'Medication details not recorded');
  }
  return String(raw || 'Medication details not recorded');
}

export function PatientCareLoop(props: Props): string {
  const currentDay = new Date();
  const todayValue = `${currentDay.getFullYear()}-${String(currentDay.getMonth() + 1).padStart(2, '0')}-${String(currentDay.getDate()).padStart(2, '0')}`;
  const nextPlan = [...props.surveillance]
    .filter((plan) => plan.target_follow_up_date >= todayValue && !['COMPLETED', 'CANCELLED'].includes(plan.status.toUpperCase()))
    .sort((a, b) => a.target_follow_up_date.localeCompare(b.target_follow_up_date))[0];
  const entries = [...props.events].sort((a, b) =>
    new Date(b.occurred_at || 0).getTime() - new Date(a.occurred_at || 0).getTime(),
  );
  const categories = [...new Set(entries.map(category))];
  const filters = ['all', ...categories];
  const history = entries.length
    ? `<div class="feed-filters" data-feed-controls="careloop" aria-label="Filter care history">${filters.map((filter) =>
      `<button class="feed-filter ${filter === 'all' ? 'active' : ''}" type="button" data-feed-filter="${filter}" data-feed-name="careloop" aria-pressed="${filter === 'all'}">${filter === 'all' ? 'All updates' : categoryLabel(filter)}</button>`,
    ).join('')}</div><div class="care-feed">${entries.map((event, index) => {
      const type = String(event.event_type || 'CARE_UPDATE');
      const state = String(event.status || 'RECORDED').replace(/_/g, ' ').toLowerCase();
      const title = type.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (letter: string) => letter.toUpperCase());
      return `<article class="care-feed-item" data-feed-item="careloop" data-feed-category="${category(event)}"><span class="feed-marker feed-marker-${category(event)}" aria-hidden="true">${category(event) === 'mri' ? 'M' : category(event) === 'symptoms' ? '+' : category(event) === 'nutrition' ? 'N' : category(event) === 'medication' ? 'Rx' : category(event) === 'surveillance' ? '↗' : '•'}</span><div class="care-feed-content"><div class="care-feed-meta"><span>${escapeHtml(categoryLabel(category(event)))}</span><time>${escapeHtml(displayDate(event.occurred_at))}</time></div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(event.summary || 'A care update was recorded.')}</p><span class="pill ${state === 'completed' ? 'green' : 'blue'}">${escapeHtml(state)}</span>${index === 0 ? '<span class="care-latest">Latest</span>' : ''}</div></article>`;
    }).join('')}</div>`
    : '<div class="care-empty"><span class="care-empty-icon" aria-hidden="true">✦</span><b>Your care updates will appear here</b><p>As activities are recorded, this page will build a dated view of your care.</p></div>';

  const newestNote = [...props.notes].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )[0];
  const recentSymptoms = [...props.symptoms]
    .sort((a, b) => new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime())
    .slice(0, 3);
  const medicationList = props.medications.length
    ? `<ul class="care-medication-list">${props.medications.slice(0, 3).map((record) =>
      `<li><span><b>${escapeHtml(medicationName(record))}</b><small>${escapeHtml(record.medication_status.replace(/_/g, ' ').toLowerCase())}</small></span><span class="pill ${record.verification_status === 'VERIFIED' ? 'green' : 'amber'}">${record.verification_status === 'VERIFIED' ? 'Verified' : 'Needs review'}</span></li>`,
    ).join('')}</ul>`
    : '<p class="muted">No medication records are available.</p>';
  const symptomList = recentSymptoms.length
    ? `<div class="care-symptom-preview">${recentSymptoms.map((symptom) =>
      `<article><span class="symptom-severity-dot severity-${symptom.severity == null ? 'unknown' : symptom.severity <= 3 ? 'mild' : symptom.severity <= 6 ? 'moderate' : 'severe'}" aria-hidden="true"></span><div><b>${escapeHtml(symptom.symptom_type)}</b><small>${escapeHtml(displayDate(symptom.onset_date || symptom.recorded_at))} · ${symptom.severity == null ? 'Severity not recorded' : `${symptom.severity}/10`} · ${escapeHtml(symptom.review_status.replace(/_/g, ' ').toLowerCase())}</small></div></article>`,
    ).join('')}</div>`
    : '<p class="muted">No symptoms recorded yet.</p>';

  return `<header class="page-head"><div><p class="eyebrow">YOUR CARE JOURNEY</p><h1>CareLoop</h1><p class="muted">A clear view of the updates and activities recorded in your care.</p></div><button class="button primary" type="button" data-go="Symptoms">+ Log a symptom</button></header>
    <section class="care-overview" aria-label="Care overview">
      <article class="care-overview-card"><span class="care-overview-icon" aria-hidden="true">◷</span><div><small>Next follow-up</small><b>${nextPlan ? escapeHtml(displayDate(nextPlan.target_follow_up_date)) : 'Not scheduled'}</b><span>${nextPlan ? escapeHtml(nextPlan.reason) : 'No upcoming plan recorded'}</span></div></article>
      <article class="care-overview-card"><span class="care-overview-icon" aria-hidden="true">⌁</span><div><small>Symptoms recorded</small><b>${props.symptoms.length}</b><span>Patient-reported entries</span></div></article>
      <article class="care-overview-card"><span class="care-overview-icon" aria-hidden="true">Rx</span><div><small>Medication records</small><b>${props.medications.length}</b><span>${props.medications.filter((item) => item.verification_status === 'VERIFIED').length} verified · ${props.medications.filter((item) => item.verification_status !== 'VERIFIED').length} awaiting review</span></div></article>
      <article class="care-overview-card"><span class="care-overview-icon" aria-hidden="true">✚</span><div><small>Latest MRI record</small><b>${props.hasAssessment ? 'MRI assessment saved' : 'No assessment'}</b><span>For clinician review</span></div></article>
    </section>
    <section class="care-shortcuts" aria-label="Care shortcuts">
      <button type="button" data-go="Symptoms"><span aria-hidden="true">＋</span><b>Log symptoms</b><small>Record how you feel</small></button>
      <button type="button" data-go="Medications"><span aria-hidden="true">Rx</span><b>Medication list</b><small>View review status</small></button>
      <button type="button" data-go="Nutrition"><span aria-hidden="true">◒</span><b>Nutrition</b><small>Review recorded meals</small></button>
      <button type="button" data-go="Timeline"><span aria-hidden="true">↗</span><b>Health timeline</b><small>See dated records</small></button>
    </section>
    <section class="care-detail-grid">
      <article class="care-detail-card"><div class="section-title"><div><p class="eyebrow">PATIENT-REPORTED</p><h2>Recent symptoms</h2></div><button class="text-button" type="button" data-go="Symptoms">View all →</button></div>${symptomList}</article>
      <article class="care-detail-card"><div class="section-title"><div><p class="eyebrow">MEDICATION RECORDS</p><h2>Your medications</h2></div><button class="text-button" type="button" data-go="Medications">View list →</button></div>${medicationList}<p class="care-detail-note">Extracted details remain marked for review until clinician-verified.</p></article>
    </section>
    <section class="card care-symptom-log"><div class="section-title"><div><p class="eyebrow">QUICK CHECK-IN</p><h2>Log a symptom</h2></div><span class="pill blue">Patient-reported</span></div><p class="muted">Choose a severity and date. Your care team can review the entry.</p><form id="symptom-form" class="care-symptom-form"><label>Symptom<input name="name" required maxlength="64" placeholder="For example, nausea"></label><fieldset class="severity-options"><legend>How severe does it feel?</legend><label><input type="radio" name="severity" value="Mild" required><span><i class="symptom-severity-dot severity-mild"></i><b>Mild</b><small>1–3</small></span></label><label><input type="radio" name="severity" value="Moderate"><span><i class="symptom-severity-dot severity-moderate"></i><b>Moderate</b><small>4–6</small></span></label><label><input type="radio" name="severity" value="Severe"><span><i class="symptom-severity-dot severity-severe"></i><b>Severe</b><small>7–10</small></span></label></fieldset><label>Date<input name="date" type="date" value="${todayValue}" required></label><label>Optional note<input name="note" maxlength="2000" placeholder="Add context for your care team"></label><div class="care-symptom-submit"><button class="button primary" type="submit">Save symptom entry</button><span class="muted">Saved to your patient-reported symptom history.</span></div></form></section>
    <section class="card care-history"><div class="section-title"><div><p class="eyebrow">RECORDED ACTIVITY</p><h2>Care history</h2></div><span class="pill blue">${entries.length} ${entries.length === 1 ? 'update' : 'updates'}</span></div>${newestNote ? `<details class="care-note-preview"><summary>Latest note · ${escapeHtml(displayDate(newestNote.created_at))}</summary><p>${escapeHtml(newestNote.body)}</p></details>` : ''}${history}<p class="care-disclaimer">Updates reflect information saved to your record; they are not medical advice. Ask your care team about clinical decisions.</p></section>`;
}
