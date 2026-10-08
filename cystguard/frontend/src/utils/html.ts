export function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] || char);
}
export function displayDate(value: string | null | undefined): string { return value ? new Date(value).toLocaleDateString() : 'Not recorded'; }
export function pageHeader(title: string, description: string): string { return `<header class="page-head"><div><p class="eyebrow">CYSTGUARD CARE</p><h1>${escapeHtml(title)}</h1><p class="muted">${escapeHtml(description)}</p></div></header>`; }
export function contentCard(title: string, body: string): string { return `<section class="card"><h2>${escapeHtml(title)}</h2>${body}</section>`; }
