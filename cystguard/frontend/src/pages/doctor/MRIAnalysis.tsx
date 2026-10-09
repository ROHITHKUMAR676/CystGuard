import { RiskCard } from '../../components/RiskCard.js';
import type { MRIAnalysisResponse } from '../../types/patient.js';
import type { UploadFlowState } from '../../components/UploadProgress.js';
import { UploadProgress } from '../../components/UploadProgress.js';
import { escapeHtml } from '../../utils/html.js';
export function DoctorMRIAnalysis(props: { result?: MRIAnalysisResponse | null; busy?: boolean; flow?: UploadFlowState | null }): string {
  const disabled = props.busy || props.flow?.status === 'uploading' || props.flow?.status === 'processing';
  return `<header class="page-head"><div><p class="eyebrow">MRI WORKFLOW</p><h1>MRI analysis</h1><p class="muted">Cyst-X expects a T1-weighted, cropped pancreatic/IPMN ROI. Full abdominal scans are not segmented or cropped by this workflow.</p></div></header><section class="card upload-card"><h2>Upload MRI scan</h2><p>Accepted format: NIfTI (.nii)</p><label class="file-picker">Choose MRI file<input id="mri-file" type="file" accept=".nii" ${disabled ? 'disabled' : ''}></label><div id="validation" class="validation"></div><p id="file-status" class="muted">No file selected</p><div class="actions"><button class="button primary" data-action="start-analysis" ${disabled ? 'disabled' : ''}>${disabled ? 'Analysis in progress…' : 'Upload and analyze'}</button></div>${UploadProgress(props.flow)}</section>${props.result ? `<section class="card upload-result"><p class="eyebrow">SAVED MRI RESULT</p><h2>${escapeHtml(props.result.mri_study.original_filename)}</h2><p class="muted">Study ${escapeHtml(props.result.mri_study.id)} · ${escapeHtml(props.result.mri_study.study_date || 'Date not recorded')}</p>${RiskCard({ ...props.result.assessment, modality: props.result.mri_study.modality })}</section>` : ''}`;
}
