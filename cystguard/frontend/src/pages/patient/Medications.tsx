import type { MedicationRecord } from '../../types/patient.js';
import { MedicationCard } from '../../components/MedicationCard.js';
import type { UploadFlowState } from '../../components/UploadProgress.js';
import { UploadProgress } from '../../components/UploadProgress.js';
import { escapeHtml } from '../../utils/html.js';

type MedicationUpload = { document?: { original_filename: string; extraction_method: string; extraction_confidence: number | null; page_count: number; raw_text: string; verification_status: string }; medications?: MedicationRecord[] };

export function PatientMedications(props: { records: MedicationRecord[]; flow?: UploadFlowState | null; latestUpload?: MedicationUpload | null }): string {
  const document = props.latestUpload?.document;
  const extracted = props.latestUpload?.medications || [];
  const text = document?.raw_text?.trim() || '';
  const result = document ? `<section class="card upload-result"><p class="eyebrow">OCR RESULT</p><h2>${escapeHtml(document.original_filename)}</h2><p class="muted">${escapeHtml(document.extraction_method)} · ${document.page_count} page(s) · ${escapeHtml(document.verification_status)}</p>${extracted.length ? `<h3>${extracted.length} medication candidate${extracted.length === 1 ? '' : 's'} found</h3>${extracted.map(record => MedicationCard(record, 'patient')).join('')}` : `<div class="empty">${text ? 'The document text was read, but no medication name could be confidently matched. Review the source text below.' : 'No readable text was extracted from this document. Try a clearer, selectable PDF or a higher quality scan.'}</div>`}${text ? `<details class="ocr-source"><summary>Review extracted document text</summary><pre>${escapeHtml(text)}</pre></details>` : ''}</section>` : '';
  return `<header class="page-head"><div><p class="eyebrow">MEDICATION RECORDS</p><h1>Medications</h1><p class="muted">Upload a prescription or medication list. Extracted details remain unverified until reviewed.</p></div></header><section class="card upload-card"><h2>Upload medication document</h2><form id="medication-upload-form" class="upload-form"><label>Choose document<input type="file" name="upload" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" required ${props.flow?.status === 'uploading' || props.flow?.status === 'processing' ? 'disabled' : ''}></label><button class="button primary" ${props.flow?.status === 'uploading' || props.flow?.status === 'processing' ? 'disabled' : ''}>${props.flow?.status === 'uploading' || props.flow?.status === 'processing' ? 'Working…' : 'Upload and extract'}</button></form>${UploadProgress(props.flow)}</section>${result}<section class="card"><h2>Medication history</h2>${props.records.length ? props.records.map((record)=>MedicationCard(record,'patient')).join('') : '<div class="empty">No medication records are stored.</div>'}</section>`;
}
