import type { MedicationRecord } from '../../types/patient.js';
import { MedicationCard } from '../../components/MedicationCard.js';
export function PatientMedications(props: { records: MedicationRecord[] }): string {
  return `<header class="page-head"><div><p class="eyebrow">MEDICATION RECORDS</p><h1>Medications</h1><p class="muted">Extracted entries keep their verification status.</p></div></header><section class="card"><h2>Upload medication document</h2><form id="medication-upload-form"><label>Choose document<input type="file" name="upload" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" required></label><button class="button primary">Upload and extract</button></form></section><section class="card"><h2>Medication history</h2>${props.records.length ? props.records.map((record)=>MedicationCard(record,'patient')).join('') : '<div class="empty">No medication records are stored.</div>'}</section>`;
}
