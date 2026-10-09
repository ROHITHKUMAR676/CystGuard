import type { AIResult } from '../types/assessment.js';
import { escapeHtml } from '../utils/html.js';

type RiskCardInput = Partial<AIResult> & { modality?: string; riskClass?: string | null; score?: number | null; modelId?: string; modelVersion?: string; predictionStatus?: string; inputQualityStatus?: string; fallbackUsed?: boolean };

export function RiskCard(result: RiskCardInput = {}): string {
  const code = result.risk_class ?? result.riskClass;
  const rawScore = result.raw_score ?? result.score;
  const profile = code === 'HIGH_RISK' ? 'Higher Risk Profile' : code === 'NO_LOW_RISK' ? 'No / Low Risk Profile' : 'Risk profile unavailable';
  const className = code === 'HIGH_RISK' ? 'risk-high' : code === 'NO_LOW_RISK' ? 'risk-low' : '';
  const identity = [result.model_id || result.modelId || 'Model not recorded', result.model_version || result.modelVersion || 'Version not recorded', result.architecture || 'Architecture not recorded', result.modality || 'Modality not recorded'].map(escapeHtml).join(' · ');
  return `<section class="risk-summary ${className}" aria-label="AI result"><div class="risk-heading"><span class="risk-icon">AI</span><div><span class="eyebrow">AI EVIDENCE</span><h3>${profile}</h3><p class="muted">${identity}</p></div></div><div class="meta"><span>AI model score <b>${rawScore == null ? 'Not recorded' : Number(rawScore).toFixed(3)}</b></span><span>Threshold <b>${result.threshold == null ? 'Not recorded' : Number(result.threshold).toFixed(3)}</b></span><span>Prediction <b>${escapeHtml(result.prediction_status || result.predictionStatus || 'UNKNOWN')}</b></span><span>Input quality <b>${escapeHtml(result.input_quality_status || result.inputQualityStatus || 'UNKNOWN')}</b></span><span>Fallback <b>${result.fallback_used == null && result.fallbackUsed == null ? 'Not recorded' : result.fallback_used || result.fallbackUsed ? 'Used' : 'Not used'}</b></span></div><p class="muted">The model score is raw model output and is not a cancer probability. Input-quality status reflects technical file checks; it does not verify modality or ROI suitability.</p></section>`;
}
