import type { ConcordanceAssessment } from '../types/assessment.js';
import { escapeHtml } from '../utils/html.js';
export function ConcordanceCard(data: ConcordanceAssessment = { status: 'UNKNOWN' }): string {
  const needsReview = data.status === 'DISCORDANT' || data.status === 'UNCERTAIN' || data.status === 'REVIEW' || data.status === 'INDETERMINATE';
  return `<section class="card"><h2>AI and guideline concordance</h2><div class="patient-row"><span>AI evidence</span><b>+</b><span>Guideline assessment</span><b>${escapeHtml(data.status)}</b></div>${needsReview ? '<div class="review-alert"><b>Review required</b><br>Review the stored AI evidence and guideline assessment.</div>' : ''}${data.reason_codes?.length ? `<ul>${data.reason_codes.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>` : '<p class="muted">No backend concordance result is stored.</p>'}</section>`;
}
