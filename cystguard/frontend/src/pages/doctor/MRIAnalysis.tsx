import { RiskCard } from '../../components/RiskCard.js';
import type { MRIAnalysisResponse } from '../../types/patient.js';
import { escapeHtml } from '../../utils/html.js';
export function DoctorMRIAnalysis(props: { result?: MRIAnalysisResponse | null; busy?: boolean }): string {
  return `<header class="page-head"><div><p class="eyebrow">MRI WORKFLOW</p><h1>MRI analysis</h1><p class="muted">Select a single-file NIfTI scan to upload.</p></div></header><section class="card"><h2>Upload MRI scan</h2><p>Accepted format: NIfTI (.nii)</p><input id="mri-file" type="file" accept=".nii"><div id="validation" class="validation"></div><p id="file-status" class="muted">No file selected</p><div class="actions"><button class="button primary" data-action="start-analysis" ${props.busy ? 'disabled' : ''}>${props.busy ? 'Analysis running' : 'Start analysis'}</button></div></section>${props.result ? `<section class="card"><h2>Stored result</h2>${RiskCard({ ...props.result.assessment, modality: props.result.mri_study.modality })}</section>` : ''}<p class="muted">${escapeHtml(props.busy ? 'Waiting for the backend result.' : 'Results appear after backend processing.')}</p>`;
}
