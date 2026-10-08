import type { MedicationRecord } from '../types/patient.js';
import { escapeHtml } from '../utils/html.js';
export function MedicationVerification(record: MedicationRecord): string {
  const fields = record.verified_fields || record.extracted_fields;
  const conflict = record.conflicts?.find((entry) => entry.status === 'CONFLICT_REQUIRES_REVIEW');
  const allowed = new Set(['name', 'generic_name', 'brand_name', 'strength', 'normalized_strength', 'dose', 'dosage_form', 'frequency', 'normalized_frequency', 'route', 'normalized_route', 'start_date', 'end_date', 'duration', 'prescriber', 'indication']);
  const inputs = Object.entries(fields).filter(([key]) => allowed.has(key)).map(([key, value]) => {
    const candidate = value && typeof value === 'object' && 'value' in value ? (value as { value: unknown }).value : value;
    return `<label>${escapeHtml(key.replace(/_/g, ' '))}<input name="${escapeHtml(key)}" value="${escapeHtml(candidate)}"></label>`;
  }).join('');
  return `<section class="card"><h3>Medication source review</h3><p>Document ${escapeHtml(record.source_document_id)} · ${escapeHtml(record.verification_status)}</p>${conflict ? `<div class="review-alert"><b>Conflict detected</b><span>Review both source records before selecting a resolved source.</span>${Object.entries(conflict.conflicting_fields || {}).map(([key, values]) => `<p>${escapeHtml(key)}: ${escapeHtml(String(values[0]))} / ${escapeHtml(String(values[1]))}</p>`).join('')}</div>` : ''}<form id="medication-verify-form" data-medication-id="${escapeHtml(record.id)}"><div class="form-grid">${inputs}</div><label>Lifecycle status<select name="medication_status"><option value="UNKNOWN">Unknown</option><option value="ACTIVE">Active</option><option value="HISTORICAL">Historical</option><option value="ENDED">Ended</option><option value="DISCONTINUED">Discontinued</option></select></label><label>Clinician note<textarea name="doctor_note" maxlength="2000"></textarea></label><button class="button primary">Verify medication</button><p class="error hidden" id="api-error"></p></form></section>`;
}
