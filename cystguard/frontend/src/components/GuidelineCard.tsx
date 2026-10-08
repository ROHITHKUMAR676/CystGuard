import type { GuidelineAssessment } from '../types/assessment.js';
import { escapeHtml } from '../utils/html.js';
const label = (value: string) => value.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (char: string) => char.toUpperCase());
function findings(title: string, values: Record<string, string> | undefined): string {
  if (!values || !Object.keys(values).length) return `<p class="muted">${title}: no persisted findings.</p>`;
  return `<h3>${title}</h3><ul>${Object.entries(values).map(([name, value]) => `<li><span>${escapeHtml(label(name))}</span><b>${escapeHtml(value)}</b></li>`).join('')}</ul>`;
}
export function GuidelineCard(data: GuidelineAssessment = { status: 'UNKNOWN' }): string {
  return `<section class="card"><h2>Kyoto 2024 assessment</h2><p>Classification: <b>${escapeHtml(data.classification || (data.status === 'UNKNOWN' ? 'Not recorded' : label(data.status)))}</b></p>${findings('High-risk stigmata', data.hrs)}${findings('Worrisome features', data.wf)}<p class="muted">Only stored backend findings are shown. Unrecorded items remain unknown.</p></section>`;
}
