import { escapeHtml } from '../utils/html.js';

export interface UploadFlowState {
  status: 'uploading' | 'processing' | 'complete' | 'error';
  progress: number;
  filename: string;
  message?: string;
}

export function UploadProgress(flow?: UploadFlowState | null): string {
  if (!flow) return '';
  const complete = flow.status === 'complete';
  const failed = flow.status === 'error';
  const label = complete ? 'Complete' : failed ? 'Needs attention' : flow.status === 'processing' ? 'Processing' : 'Uploading';
  const headline = complete ? 'Results are ready' : failed ? 'We could not finish this upload' : flow.status === 'processing' ? 'File received · processing results' : 'Uploading your file';
  const progress = Math.max(0, Math.min(100, flow.progress));
  return `<section class="upload-progress ${failed ? 'failed' : complete ? 'complete' : ''}" role="status" aria-live="polite">
    <div class="upload-progress-heading"><div><span class="eyebrow">${label}</span><h3>${headline}</h3><p>${escapeHtml(flow.filename)}${flow.message ? ` · ${escapeHtml(flow.message)}` : ''}</p></div><b>${failed ? '!' : `${progress}%`}</b></div>
    <div class="progress-track" role="progressbar" aria-label="${label}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><i style="width:${progress}%"></i></div>
    <div class="upload-progress-steps"><span class="${progress > 0 ? 'done' : ''}">File transfer</span><span class="${flow.status === 'processing' || complete ? 'current' : ''}">Extract and process</span><span class="${complete ? 'done' : ''}">Show results</span></div>
    ${failed ? `<p class="error" role="alert">${escapeHtml(flow.message || 'Please check the file and try again.')}</p>` : ''}
  </section>`;
}
