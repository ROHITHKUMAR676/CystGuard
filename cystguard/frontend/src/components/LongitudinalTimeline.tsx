import type { MRIStudySummary } from '../types/patient.js';
import { displayDate, escapeHtml } from '../utils/html.js';

export function LongitudinalTimeline(props: { studies: MRIStudySummary[]; orderingComplete?: boolean }): string {
  if (!props.studies.length) return '<div class="empty">No patient-linked MRI studies are stored.</div>';

  const studies = [...props.studies].sort((a, b) =>
    new Date(a.study_date || a.uploaded_at).getTime() - new Date(b.study_date || b.uploaded_at).getTime(),
  );
  const entries = studies.map((study, index) => {
    const result = study.assessments?.[0];
    const rawScore = result?.raw_score;
    const score = typeof rawScore === 'number' && Number.isFinite(rawScore) && rawScore >= 0 && rawScore <= 1
      ? rawScore
      : null;
    const date = study.study_date || study.uploaded_at;
    return { study, result, index, score, date };
  });

  const chartEntries = entries.filter((entry) => entry.score !== null);
  const chartWidth = Math.max(560, 140 * Math.max(entries.length - 1, 1) + 120);
  const left = 72;
  const right = chartWidth - 36;
  const xAt = (index: number) => entries.length === 1
    ? (left + right) / 2
    : left + (index * (right - left)) / (entries.length - 1);
  const yAt = (score: number) => 244 - score * 190;
  const line = chartEntries.map(({ score, index }, pointIndex) => `${pointIndex ? 'L' : 'M'} ${xAt(index)} ${yAt(score!)}`).join(' ');
  const chart = chartEntries.length
    ? `<div class="longitudinal-chart"><svg viewBox="0 0 ${chartWidth} 320" role="img" aria-label="Line graph of raw MRI model score by study. Scores are not probabilities.">
        <text class="chart-axis-title" x="18" y="145" transform="rotate(-90 18 145)">Raw model score (0–1)</text>
        ${[0, 0.25, 0.5, 0.75, 1].map((tick) => { const y = yAt(tick); return `<line class="chart-gridline" x1="${left}" y1="${y}" x2="${right}" y2="${y}"/><text class="chart-tick" x="${left - 12}" y="${y + 4}" text-anchor="end">${tick.toFixed(2)}</text>`; }).join('')}
        <path class="chart-line" d="${line}"/>
        ${entries.map(({ score, index, date, study }) => { const x = xAt(index); const y = score === null ? 244 : yAt(score); return `<g><text class="chart-x-label" x="${x}" y="278" text-anchor="middle">MRI ${index + 1}</text><text class="chart-date-label" x="${x}" y="298" text-anchor="middle">${escapeHtml(displayDate(date))}${study.study_date ? '' : ' · upload'}</text>${score === null ? '<text class="chart-missing" x="' + x + '" y="236" text-anchor="middle">No score</text>' : `<circle class="chart-point" cx="${x}" cy="${y}" r="6"/><text class="chart-value-label" x="${x}" y="${y - 13}" text-anchor="middle">${score.toFixed(3)}</text>`}</g>`; }).join('')}
      </svg></div><p class="muted longitudinal-caption">Raw model score (0–1), not a probability.</p>`
    : '<div class="empty">No model scores are recorded for these studies.</div>';

  const records = entries.map(({ study, result, index }) => {
    const profile = result?.risk_class === 'HIGH_RISK'
      ? 'Higher risk profile'
      : result?.risk_class === 'NO_LOW_RISK'
        ? 'No / low risk profile'
        : 'Assessment unavailable';
    const measurements = (study.measurements || []).map((measurement) =>
      `<li><b>${escapeHtml(String(measurement.feature || 'Measurement'))}</b><span>${measurement.value == null ? escapeHtml(String(measurement.finding_status || 'Unknown')) : `${escapeHtml(String(measurement.value))} ${escapeHtml(String(measurement.unit || ''))}`}</span><small>${escapeHtml(String(measurement.source || 'Source not recorded'))}</small></li>`,
    ).join('');
    return `<article class="longitudinal-record"><div class="longitudinal-record-heading"><div><span class="eyebrow">MRI ${index + 1}</span><p class="longitudinal-record-date">${escapeHtml(displayDate(study.study_date || study.uploaded_at))}${study.study_date ? '' : ' · upload date'}</p></div><span class="longitudinal-profile">${profile}</span></div><div class="longitudinal-record-score"><span>Raw model score</span><strong>${result?.raw_score == null ? 'Not recorded' : Number(result.raw_score).toFixed(3)}</strong><small>Not a probability</small></div>${measurements ? `<div class="longitudinal-measurements"><h4>Recorded measurements</h4><ul>${measurements}</ul></div>` : ''}</article>`;
  }).join('');

  return `${chart}<div class="longitudinal-records">${records}</div>${props.orderingComplete === false ? '<p class="muted">Some study dates are missing; upload dates are used where available.</p>' : ''}`;
}
