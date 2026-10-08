const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function RiskCard({ score = 0.72, threshold = 0.5, date = '18 Sep 2026' } = {}) {
  const high = score >= threshold;
  return `<div class="risk-summary ${high ? 'risk-high' : 'risk-low'}"><div class="risk-heading"><span class="risk-icon">${high ? '!' : '✓'}</span><div><span class="eyebrow">AI EVIDENCE · CYST-X</span><h3>${high ? 'Higher Risk Profile' : 'No / Low Risk Profile'}</h3><p class="muted">3D DenseNet-121 · T1 MRI</p></div><div class="score"><b>${score.toFixed(2)}</b><small>AI model score</small></div></div><div class="meter"><i style="width:${Math.max(0,Math.min(100,score*100))}%"></i></div><div class="meta"><span>Review threshold <b>${threshold.toFixed(2)}</b></span><span>Analysis date <b>${escapeHtml(date)}</b></span></div><p class="muted">Model score is imaging evidence for clinical review, not a cancer probability.</p></div>`;
}

export function AnalysisProgress({ analysis, stages }) {
  if (analysis.status === 'idle') return `<div class="analysis-idle"><div class="progress-orb">0<span>%</span></div><div><b>Ready to begin</b><p class="muted">Validation, preprocessing, model analysis, and evidence review are shown below.</p></div></div>`;
  return `<div class="progress-head"><div><span class="eyebrow">${analysis.status==='complete'?'ANALYSIS COMPLETE':'ANALYSIS IN PROGRESS'}</span><h3>${analysis.status==='complete'?'Review the assessment':'Processing MRI study'}</h3></div><b class="progress-value">${analysis.progress}%</b></div><div class="progress-track"><i style="width:${analysis.progress}%"></i></div><div class="analysis-stages">${stages.map((name,i)=>`<div class="analysis-stage ${i<analysis.stage||analysis.status==='complete'?'complete':i===analysis.stage?'current':''}"><span>${i<analysis.stage||analysis.status==='complete'?'✓':String(i+1).padStart(2,'0')}</span><div><b>${escapeHtml(name)}</b><small>${i<analysis.stage||analysis.status==='complete'?'Complete':i===analysis.stage&&analysis.status==='running'?'In progress':'Waiting'}</small></div></div>`).join('')}</div>`;
}

export function AccessRequestCard({ request, index, controls = false }) {
  const initials = escapeHtml(request.name.split(/\s+/).map(part=>part[0]).join('').slice(0,2));
  return `<div class="access-request"><div class="avatar">${initials}</div><div class="grow"><b>${escapeHtml(request.name)}</b><small>${escapeHtml(request.patientId)} · request ${escapeHtml(request.reference)}</small><small>Received ${escapeHtml(request.createdAt)}</small></div><span class="pill ${request.status==='Approved'?'green':request.status==='Pending'?'amber':'red'}">${escapeHtml(request.status)}</span>${controls&&request.status==='Pending'?`<button class="button primary" data-approve="${index}">Approve access</button><button class="button" data-deny="${index}">Decline</button>`:''}</div>`;
}
