import { ConcordanceCard } from '../../components/ConcordanceCard.js';
import { GuidelineCard } from '../../components/GuidelineCard.js';
import { LongitudinalTimeline } from '../../components/LongitudinalTimeline.js';
import { RiskCard } from '../../components/RiskCard.js';
import { UncertaintyCard } from '../../components/UncertaintyCard.js';
import type { AIResult } from '../../types/assessment.js';
import type { MRIStudySummary } from '../../types/patient.js';
import { ExplanationPanel } from '../../components/ExplanationPanel.js';
import { ClinicalContextForm } from '../../components/ClinicalContextForm.js';
import { escapeHtml } from '../../utils/html.js';
export function DoctorAssessmentPage(props: { result?: AIResult | null; studies: MRIStudySummary[]; note?: string }): string {
  const result = props.result || null;
  const guideline: any = result?.guideline || {};
  const trust: any = result?.trust || {};
  const concordance: any = trust.concordance || {};
  const guidelineCard = result?.guideline ? GuidelineCard({ status: guideline.not_applicable ? 'NOT_APPLICABLE' : guideline.assessment_status === 'PARTIALLY_EVALUATED' || guideline.assessment_status === 'NOT_EVALUABLE' ? 'INCOMPLETE' : 'AVAILABLE', classification: guideline.assessment_status, hrs: Object.fromEntries((guideline.high_risk_stigmata || []).map((item: any) => [item.rule_code, item.status])), wf: Object.fromEntries((guideline.worrisome_features || []).map((item: any) => [item.rule_code, item.status])) }) : GuidelineCard({ status: 'UNKNOWN' });
  const trustCard = result?.trust ? UncertaintyCard({ status: 'AVAILABLE', method: trust.trust_engine?.name ? `${trust.trust_engine.name} ${trust.trust_engine.version}` : 'CystGuard trust service', reliability: trust.doctor_review_required ? 'Review recommended' : 'Evaluated', review_required: trust.doctor_review_required, calibration: trust.calibration?.status === 'CALIBRATED' ? 'Validated' : 'Not validated' }) : UncertaintyCard({ status: 'UNKNOWN' });
  const concordanceCard = result?.trust ? ConcordanceCard({ status: concordance.status, reason_codes: concordance.reason_codes }) : ConcordanceCard({ status: 'UNKNOWN' });
  return `<header class="page-head"><div><p class="eyebrow">CLINICIAN REVIEW</p><h1>Assessment</h1><p class="muted">AI evidence, guideline facts, and clinician review remain distinct.</p></div></header>${props.result ? RiskCard(props.result) : '<section class="card"><div class="empty">No MRI assessment is stored.</div></section>'}${ExplanationPanel(result)}${result ? ClinicalContextForm({ assessmentId: result.id, context: result.clinical_context }) : ''}<div class="grid two">${guidelineCard}${trustCard}${concordanceCard}</div><section class="card"><h2>Longitudinal MRI</h2>${LongitudinalTimeline({ studies: props.studies })}</section><section class="card"><h2>Clinician assessment</h2><label>Review status<select id="clinician-assessment" name="status"><option value="">Choose review status</option><option>Reviewed</option><option>Discuss at multidisciplinary review</option><option>Additional evaluation needed</option></select></label><label>Clinical note<textarea id="clinical-notes" name="note" maxlength="10000">${escapeHtml(props.note)}</textarea></label><button type="button" class="button primary" data-action="review">Save clinician review</button></section>`;
}
