import type { MedicationRecord } from '../types/patient.js';
import { escapeHtml } from '../utils/html.js';
type FieldValue = { value?: unknown; normalized_value?: unknown } | string | number | null;
function value(fields: Record<string, unknown>, key: string): string {
  const raw = fields[key] as FieldValue;
  if (raw && typeof raw === 'object' && 'value' in raw) return String(raw.normalized_value ?? raw.value ?? 'Not recorded');
  return raw == null || raw === '' ? 'Not recorded' : String(raw);
}
export function MedicationCard(record: MedicationRecord, role: 'doctor' | 'patient' = 'patient'): string {
  const fields = record.verified_fields || record.extracted_fields;
  const conflicts = role === 'patient' ? (record.conflicts || []).filter((item) => item.status === 'CONFLICT_REQUIRES_REVIEW').map((item) => `<form id="medication-conflict-form" data-medication-id="${escapeHtml(record.id)}"><div class="review-alert"><b>Medication conflict detected</b><span>Review the source values below and select the source that matches your record. A clinician still reviews medication details.</span>${Object.entries(item.conflicting_fields || {}).map(([key, pair]) => `<p>${escapeHtml(key)}: ${escapeHtml(String(pair[0]))} / ${escapeHtml(String(pair[1]))}</p>`).join('')}<label>Preferred source<select name="resolution_record_id"><option value="${escapeHtml(item.medication_record_ids[0])}">Source 1 · ${escapeHtml(item.medication_record_ids[0])}</option><option value="${escapeHtml(item.medication_record_ids[1])}">Source 2 · ${escapeHtml(item.medication_record_ids[1])}</option></select></label><label>Review note<textarea name="review_note" required maxlength="2000"></textarea></label><button class="button">Save source review</button></div></form>`).join('') : '';
  return `<article class="patient-row"><div class="grow"><b>${escapeHtml(value(fields, 'name'))}</b><small>Generic ${escapeHtml(value(fields, 'generic_name'))} · ${escapeHtml(value(fields, 'strength'))} · ${escapeHtml(value(fields, 'frequency'))} · ${escapeHtml(value(fields, 'route'))}</small><small>Start ${escapeHtml(value(fields, 'start_date'))} · End ${escapeHtml(value(fields, 'end_date'))}</small></div><span class="pill ${record.verification_status === 'VERIFIED' ? 'green' : 'amber'}">${escapeHtml(record.verification_status)}</span><span class="pill blue">${escapeHtml(record.medication_status)}</span>${record.source_document_id ? `<small>Source document ${escapeHtml(record.source_document_id)}</small>` : ''}</article>${conflicts}`;
}
