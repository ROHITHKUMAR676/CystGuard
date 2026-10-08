import type { MRIStudySummary } from '../../types/patient.js';
import { escapeHtml } from '../../utils/html.js';
export function PatientTimeline(props: { studies: MRIStudySummary[] }): string {
  return `<header class="page-head"><div><p class="eyebrow">YOUR MRI HISTORY</p><h1>Timeline</h1><p class="muted">Study dates and record availability from your saved history.</p></div></header><section class="card"><h2>MRI timeline</h2>${props.studies.length ? props.studies.map((study,index)=>`<article class="timeline-entry"><span class="timeline-dot"></span><div><small>MRI ${index+1} · ${escapeHtml(study.study_date || 'Study date not recorded')}</small><h3>${study.assessments.length ? 'Assessment available for clinician review' : 'No assessment recorded'}</h3><p>${study.measurements.length ? 'Sourced measurements are recorded.' : 'No sourced measurements are recorded.'}</p></div></article>`).join('') : '<div class="empty">No MRI timeline items are stored.</div>'}</section>`;
}
