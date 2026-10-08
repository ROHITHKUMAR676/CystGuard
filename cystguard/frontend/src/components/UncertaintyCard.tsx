import type { TrustAssessment } from '../types/assessment.js';
import { escapeHtml } from '../utils/html.js';
export function UncertaintyCard(data: TrustAssessment = { status: 'UNKNOWN' }): string {
  return `<section class="card"><h2>Uncertainty and trust</h2><div class="meta vertical"><span>Status <b>${escapeHtml(data.status)}</b></span><span>Method <b>${escapeHtml(data.method || 'Not recorded')}</b></span><span>Reliability <b>${escapeHtml(data.reliability || 'Not evaluated')}</b></span><span>Calibration <b>${escapeHtml(data.calibration || 'Not validated')}</b></span></div>${data.review_required ? '<div class="review-alert">Review required by backend trust assessment.</div>' : ''}</section>`;
}
