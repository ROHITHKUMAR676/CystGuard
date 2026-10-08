import { escapeHtml } from '../utils/html.js';
export function ReviewAlert(props: { title: string; detail: string; level?: 'attention' | 'urgent' }): string {
  return `<aside class="review-alert ${props.level === 'urgent' ? 'review-alert-urgent' : ''}" role="status"><b>${escapeHtml(props.title)}</b><span>${escapeHtml(props.detail)}</span></aside>`;
}
