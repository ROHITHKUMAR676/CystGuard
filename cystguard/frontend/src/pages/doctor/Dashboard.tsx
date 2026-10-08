import { ReviewAlert } from '../../components/ReviewAlert.js';
import { escapeHtml } from '../../utils/html.js';

interface Patient { id: number; name: string; email?: string }
interface Overview {
  patient: Patient;
  profile: { latest_mri?: { study_date?: string | null }; latest_assessment?: { risk_class?: string | null; model_id?: string; model_version?: string } | null };
  reviews: Array<{ item_type?: string; priority?: string }>;
  plans: Array<{ target_follow_up_date?: string; reason?: string; status?: string }>;
}
interface NutritionAlert { patientId: number; patientName: string; level?: string; title?: string; summary?: string }

export function DoctorDashboard(props: {
  name: string;
  accessCode: string;
  requests: Array<{ name: string; patientId: number; index: number }>;
  overview: Overview[];
  nutritionAlerts?: NutritionAlert[];
}): string {
  const queue = props.overview.flatMap((entry) => entry.reviews.map((review) => ({ patient: entry.patient, review })));
  const assessments = props.overview.filter((entry) => entry.profile.latest_assessment);
  const followups = props.overview.flatMap((entry) => entry.plans.map((plan) => ({ patient: entry.patient, plan })));
  const nutritionAlerts = props.nutritionAlerts || [];
  const nutrition = nutritionAlerts.length
    ? nutritionAlerts.map((alert) => `<div class="nutrition-alert nutrition-alert-${escapeHtml((alert.level || 'review').toLowerCase())}"><div class="nutrition-alert-heading"><b>${escapeHtml(alert.title || 'Nutrition review recommended')}</b><button class="button" data-open-patient="${alert.patientId}">Review patient</button></div><p><strong>${escapeHtml(alert.patientName)}</strong> Â· ${escapeHtml(alert.summary || '')}</p></div>`).join('')
    : '<div class="empty">No nutrition review flags are present in the connected patient records.</div>';

  return `<header class="page-head"><div><p class="eyebrow">CLINIC WORKSPACE</p><h1>Welcome, ${escapeHtml(props.name)}</h1><p class="muted">Connected patients and persisted workflow items.</p></div><button class="button" data-action="logout">Sign out</button></header>
    <div class="stats"><div class="stat"><small>CONNECTED PATIENTS</small><b>${props.overview.length}</b></div><div class="stat"><small>REVIEW QUEUE</small><b>${queue.length}</b></div><div class="stat"><small>UPCOMING PLANS</small><b>${followups.length}</b></div><div class="stat stat-code"><small>YOUR ACCESS CODE</small><b>${escapeHtml(props.accessCode || 'Unavailable')}</b></div></div>
    ${queue.length ? ReviewAlert({ title: 'Items require review', detail: `${queue.length} open patient workflow items are recorded.` }) : ''}
    <section class="card nutrition-dashboard-card"><div class="section-heading"><div><h2>Nutrition review flags</h2><p class="muted">Patient-reported monitoring context for clinician review.</p></div><span class="pill ${nutritionAlerts.length ? 'amber' : 'green'}">${nutritionAlerts.length} flags</span></div>${nutrition}<p class="fine-print">Monitoring flags support review and are not diagnoses or treatment instructions.</p></section>
    <div class="grid two"><section class="card"><h2>Review queue</h2>${queue.length ? queue.map(({ patient, review }) => `<div class="patient-row"><div class="grow"><b>${escapeHtml(patient.name)}</b><small>${escapeHtml(review.item_type || 'Care workflow item')} Â· ${escapeHtml(review.priority || 'NORMAL')}</small></div><button class="button" data-open-patient="${patient.id}">Review</button></div>`).join('') : '<div class="empty">No open review items are stored.</div>'}</section><section class="card"><h2>Recent MRI assessments</h2>${assessments.length ? assessments.map(({ patient, profile }) => `<div class="patient-row"><div class="grow"><b>${escapeHtml(patient.name)}</b><small>${escapeHtml(profile.latest_mri?.study_date || 'Study date not recorded')} Â· ${escapeHtml(profile.latest_assessment?.model_id || 'Model not recorded')} ${escapeHtml(profile.latest_assessment?.model_version || '')}</small></div><span>${escapeHtml(profile.latest_assessment?.risk_class || 'Unavailable')}</span><button class="button" data-open-patient="${patient.id}">Open</button></div>`).join('') : '<div class="empty">No patient-linked MRI assessments are stored.</div>'}</section></div>
    <div class="grid two"><section class="card"><h2>Upcoming surveillance</h2>${followups.length ? followups.map(({ patient, plan }) => `<div class="patient-row"><div class="grow"><b>${escapeHtml(patient.name)}</b><small>${escapeHtml(plan.target_follow_up_date)} Â· ${escapeHtml(plan.reason)}</small></div><span class="pill blue">${escapeHtml(plan.status || 'PLANNED')}</span></div>`).join('') : '<div class="empty">No surveillance plans are stored.</div>'}</section><section class="card"><h2>Access requests</h2>${props.requests.length ? props.requests.map((request) => `<div class="patient-row"><div class="grow"><b>${escapeHtml(request.name)}</b><small>Patient ID ${escapeHtml(request.patientId)}</small></div><button class="button primary" data-approve="${request.index}">Approve</button></div>`).join('') : '<div class="empty">No requests are waiting for review.</div>'}</section></div>`;
}
