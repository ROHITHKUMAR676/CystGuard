import { AccessRequestCard, AnalysisProgress } from './components/ui.js';
import { RiskCard } from './components/RiskCard.js';
import { UncertaintyCard } from './components/UncertaintyCard.js';
import { GuidelineCard } from './components/GuidelineCard.js';
import { ConcordanceCard } from './components/ConcordanceCard.js';
import { ReviewAlert } from './components/ReviewAlert.js';
import { LongitudinalTimeline } from './components/LongitudinalTimeline.js';
import { MedicationCard } from './components/MedicationCard.js';
import { MedicationVerification } from './components/MedicationVerification.js';
import { MealAnalyzer } from './components/MealAnalyzer.js';
import { MealEntry } from './components/MealEntry.js';
import { NutritionTimeline } from './components/NutritionTimeline.js';
import { DoctorDashboard } from './pages/doctor/Dashboard.js';
import { DoctorPatientProfile } from './pages/doctor/PatientProfile.js';
import { DoctorMRIAnalysis } from './pages/doctor/MRIAnalysis.js';
import { DoctorAssessmentPage } from './pages/doctor/Assessment.js';
import { DoctorSurveillance } from './pages/doctor/Surveillance.js';
import { DoctorReports } from './pages/doctor/Reports.js';
import { PatientDashboard } from './pages/patient/Dashboard.js';
import { PatientCareLoop } from './pages/patient/CareLoop.js';
import { PatientSymptoms } from './pages/patient/Symptoms.js';
import { PatientMedications } from './pages/patient/Medications.js';
import { PatientMeals } from './pages/patient/Meals.js';
import { PatientTimeline } from './pages/patient/Timeline.js';
import { PatientVisitPreparation } from './pages/patient/VisitPreparation.js';
import { clinicianSeed, patientSeeds, resultForUpload, seededAccessRequests, estimateMeal } from './data/workflowSeeds.js';
import { api, apiRequest, authenticate, clearSession, getAccessToken, validateMRIFile } from './services/api.js';
import { buildClinicalContextPayload } from './utils/clinicalContext.js';

const primaryPatient = patientSeeds[0];
const initial = {
  role: null,
  patient: { ...primaryPatient },
  symptoms: [...primaryPatient.symptoms],
  questions: ['Should I continue my current follow-up interval?'],
  meals: [...primaryPatient.meals],
  messages: [{ from: 'doctor', text: 'Your latest imaging has been reviewed. We can discuss the follow-up plan at your next visit.', time: 'Today Â· 9:42 AM' }],
  kyoto: {},
  accessRequests: [...seededAccessRequests],
  patientDirectory: patientSeeds.map(person => ({ ...person, symptoms: [...person.symptoms], meals: [...person.meals] })),
  selectedPatientId: 'CG-1031',
  addPatientOpen: false,
  doctorAccessCode: clinicianSeed.accessCode,
  followups: [{ date: '2026-12-14', reason: 'MRI follow-up and care review', status: 'Upcoming' }],
  notes: '', reviewed: false, assessment: '', uploadName: '', uploadStatus: '',
  analysis: { status: 'idle', progress: 0, stage: 0 },
  uploadRunCount: 0,
  workflowVersion: 3
};
const savedState = JSON.parse(localStorage.getItem('cystguard-workflow') || '{}');
const state = Object.assign(initial, savedState);
if ((savedState.workflowVersion || 0) < 3) {
  const seededIds = new Set(seededAccessRequests.map(request => request.patientId));
  const priorRequests = Array.isArray(state.accessRequests) ? state.accessRequests : [];
  state.accessRequests = [...seededAccessRequests, ...priorRequests.filter(request => !seededIds.has(request.patientId))];
}
state.workflowVersion = 3;
state.patientDirectory ||= [];
for (const seed of patientSeeds) if (!state.patientDirectory.some(person => person.id === seed.id)) state.patientDirectory.push({ ...seed, symptoms: [...seed.symptoms], meals: [...seed.meals] });
state.accessRequests ||= [];
state.analysis ||= { status: state.uploadStatus === 'complete' ? 'complete' : 'idle', progress: state.uploadStatus === 'complete' ? 100 : 0, stage: state.uploadStatus === 'complete' ? 4 : 0 };
state.user ||= null;
state.backendConnected = false;
state.apiLoading = false;
state.apiError = '';
function patientRecord(id) { return state.patientDirectory.find(person => person.id === id) || patientSeeds.find(person => person.id === id) || (state.patient.id === id ? state.patient : null); }
function selectedPatient() { return state.role === 'doctor' ? patientRecord(state.selectedPatientId) || state.patient : state.patient; }
function patientHasApprovedAccess(id) { return state.accessRequests.some(request => request.patientId === id && request.status === 'Approved'); }
function save() {
  if (state.backendConnected) return;
  if (state.role === 'patient' && state.patient?.id) {
    const index = state.patientDirectory.findIndex(person => person.id === state.patient.id);
    const updated = { ...state.patient, symptoms: state.symptoms, meals: state.meals, latestAnalysis: state.analysis?.result || state.patient.latestAnalysis };
    if (index >= 0) state.patientDirectory[index] = updated; else state.patientDirectory.push(updated);
  }
  localStorage.setItem('cystguard-workflow', JSON.stringify(state));
}
const apiPatient = user => ({
  id: user.id, name: user.display_name || user.email.split('@')[0], email: user.email,
  age: null, diagnosis: 'Care information pending', doctorId: null, lastMri: '', nextVisit: '',
  symptoms: [], meals: [], latestAnalysis: null,
});
const accessStatusLabel = status => ({ PENDING: 'Pending', ACTIVE: 'Approved', DECLINED: 'Declined', REVOKED: 'Revoked' }[status] || status);
function accessRequestFromApi(row) {
  return { name: state.role==='patient'?(row.doctor_name||row.doctor_email):(row.patient_name||row.patient_email), patientId: row.patient_id, doctorId: row.doctor_id,
    doctorCode: row.doctor_access_code, status: accessStatusLabel(row.status), reference: `#${row.patient_id}`,
    createdAt: row.created_at ? new Date(row.created_at).toLocaleString() : '' };
}
function symptomFromApi(item) {
  const severity = item.severity == null ? 'Unknown' : item.severity <= 3 ? 'Mild' : item.severity <= 6 ? 'Moderate' : 'Severe';
  return { ...item, id: item.id, name: item.symptom_type, severityLabel: severity, date: item.onset_date || item.recorded_at?.slice(0,10) || '', note: item.notes || '', reviewStatus: item.review_status };
}
async function refreshBackendData() {
  if (!state.user) return;
  state.backendConnected = true;
  state.apiLoading = true;
  render();
  try {
    if (state.role === 'doctor') {
      const [accessRows, reports] = await Promise.all([apiRequest('/patients/access-requests'),apiRequest('/reports')]);
      state.accessRequests = accessRows.map(accessRequestFromApi);
      state.reportRecords = reports;
      state.patientDirectory = accessRows.filter(row => row.status === 'ACTIVE').map(row => ({
        id: row.patient_id, name: row.patient_name || row.patient_email, email: row.patient_email,
        diagnosis: 'Care information pending', lastMri: '', nextVisit: '', symptoms: [], meals: [],
      }));
      state.doctorOverview = await Promise.all(state.patientDirectory.map(async patient => {
        const [profile, reviews, plans, nutrition] = await Promise.all([
          apiRequest(`/patients/${patient.id}/care-profile`),
          apiRequest(`/patients/${patient.id}/reviews?status=OPEN`),
          apiRequest(`/patients/${patient.id}/surveillance`),
          apiRequest(`/patients/${patient.id}/nutrition/summary`),
        ]);
        return { patient, profile, reviews, plans, nutrition };
      }));
      state.selectedPatientId = Number(state.selectedPatientId) || state.patientDirectory[0]?.id || null;
      state.doctorAccessCode = state.user.doctor_access_code || '';
      if (state.selectedPatientId && patientHasApprovedAccess(state.selectedPatientId)) await loadSelectedDoctorPatient();
    } else {
      state.patient = apiPatient(state.user);
      state.patientDirectory = [state.patient];
      const patientId = state.user.id;
      const [profile, symptoms, accessRows, plans, meds, notes, events, timeline, meals, messages, reports, nutrition] = await Promise.all([
        apiRequest(`/patients/${patientId}/care-profile`),
        apiRequest(`/patients/${patientId}/symptoms`),
        apiRequest(`/patients/${patientId}/access-requests`),
        apiRequest(`/patients/${patientId}/surveillance`),
        apiRequest(`/patients/${patientId}/medications`),
        apiRequest(`/patients/${patientId}/notes`),
        apiRequest(`/patients/${patientId}/careloop`),
        apiRequest(`/patients/${patientId}/mri/timeline`),
        apiRequest(`/patients/${patientId}/meals`),
        apiRequest(`/patients/${patientId}/messages`),
        apiRequest('/reports'),
        apiRequest(`/patients/${patientId}/nutrition/summary`),
      ]);
      state.patient.lastMri = profile.latest_mri?.study_date || profile.latest_mri?.uploaded_at?.slice(0,10) || '';
      state.latestProfile = profile;
      state.activeDoctors = profile.active_doctors || [];
      state.patient.latestAnalysis = profile.latest_assessment ? {
        score: profile.latest_assessment.raw_score, threshold: null, riskClass: profile.latest_assessment.risk_class,
        profile: profile.latest_assessment.risk_class || 'Assessment recorded', date: profile.latest_assessment.created_at?.slice(0,10),
        studyId: profile.latest_assessment.mri_study_id, evidence: [],
      } : null;
      state.symptoms = symptoms.map(symptomFromApi);
      state.accessRequests = accessRows.map(accessRequestFromApi);
      state.followups = plans.map(plan => ({ id: plan.id, date: plan.target_follow_up_date, reason: plan.reason,
        status: plan.status === 'COMPLETED' ? 'Completed' : plan.status, backendStatus: plan.status }));
      state.medicationRecords = meds;
      state.notesFromApi = notes;
      state.questions = notes.map(note=>note.body);
      state.careEvents = events;
      state.timelineFromApi = timeline;
      state.meals = meals.map(item => ({ ...item, id: item.id, name: item.description, date: item.recorded_at?.slice(0,10) || '',
        confirmed: item.patient_confirmed, kcal: item.final_nutrition?.calories_kcal ?? item.nutrition_estimate?.calories_kcal ?? null, recordedAt: item.recorded_at }));
      state.nutritionSummary = nutrition;
      state.messages = messages.map(item => ({ id: item.id, from: item.sender_user_id === state.user.id ? 'patient' : 'doctor',
        text: item.body, time: item.created_at ? new Date(item.created_at).toLocaleString() : '' }));
      state.reportRecords = reports;
      state.patientDirectory[0] = state.patient;
    }
    state.apiError = '';
  } catch (error) {
    state.apiError = error.message;
  } finally {
    state.apiLoading = false;
    render();
  }
}
async function loadSelectedDoctorPatient() {
  if (!state.backendConnected || state.role !== 'doctor' || !state.selectedPatientId) return;
  try {
    const id = state.selectedPatientId;
    const [profile, symptoms, plans, timeline, meals, messages, medications, nutrition, reports] = await Promise.all([
      apiRequest(`/patients/${id}/care-profile`), apiRequest(`/patients/${id}/symptoms`),
      apiRequest(`/patients/${id}/surveillance`),
      apiRequest(`/patients/${id}/mri/timeline`), apiRequest(`/patients/${id}/meals`),
      apiRequest(`/patients/${id}/messages`),
      apiRequest(`/patients/${id}/medications`),
      apiRequest(`/patients/${id}/nutrition/summary`),
      apiRequest(`/reports/patients/${id}`),
    ]);
    const patient = patientRecord(id);
    if (!patient) return;
    patient.lastMri = profile.latest_mri?.study_date || profile.latest_mri?.uploaded_at?.slice(0,10) || '';
    state.latestProfile = profile;
    state.selectedPatientReports = reports;
    state.latestStudy = profile.latest_mri?.id ? await apiRequest(`/mri/studies/${encodeURIComponent(profile.latest_mri.id)}`) : null;
    patient.latestAnalysis = profile.latest_assessment ? {
      score: profile.latest_assessment.raw_score, threshold: null, riskClass: profile.latest_assessment.risk_class,
      profile: profile.latest_assessment.risk_class, date: profile.latest_assessment.created_at?.slice(0,10),
      studyId: profile.latest_assessment.mri_study_id, evidence: [],
    } : null;
    patient.symptoms = symptoms.map(symptomFromApi);
    patient.meals = meals.map(item => ({...item,id:item.id,name:item.description,date:item.recorded_at?.slice(0,10)||'',confirmed:item.patient_confirmed}));
    state.nutritionSummary = nutrition;
    patient.nextVisit = plans[0]?.target_follow_up_date || '';
    state.symptoms = patient.symptoms;
    state.meals = patient.meals;
    state.followups = plans.map(plan=>({id:plan.id,date:plan.target_follow_up_date,reason:plan.reason,status:plan.status,backendStatus:plan.status}));
    state.medicationRecords = medications;
    state.timelineFromApi = timeline;
    state.messages = messages.map(item => ({id:item.id,from:item.sender_user_id===state.user.id?'patient':'doctor',text:item.body,time:item.created_at?new Date(item.created_at).toLocaleString():''}));
    state.latestProfile = profile;
  } catch (error) {
    state.apiError = error.message;
  }
}
async function finishAuthentication(user) {
  state.user = user;
  state.backendConnected = true;
  state.role = user.role === 'DOCTOR' ? 'doctor' : 'patient';
  state.doctorAccessCode = user.doctor_access_code || '';
  state.patient = apiPatient(user);
  state.symptoms = [];
  state.meals = [];
  state.messages = [];
  state.followups = [];
  state.analysis = { status: 'idle', progress: 0, stage: 0 };
  state.questions = [];
  state.sessionRestoring = false;
  page = 'Dashboard';
  await refreshBackendData();
}
const routes = {
  doctor: ['Dashboard', 'Patients', 'Access Requests', 'Patient Profile', 'MRI Analysis', 'Assessment', 'Timeline', 'Meals', 'Nutrition', 'Surveillance', 'Reports', 'Messages'],
  patient: ['Dashboard', 'CareLoop', 'Care Team Access', 'Assessment', 'Timeline', 'Symptoms', 'Medications', 'Meals', 'Nutrition', 'Surveillance', 'Visit Preparation', 'Messages']
};
let page = 'Dashboard';
let authMode = 'login';
let authRole = 'patient';
state.role = null;
state.sessionRestoring = Boolean(getAccessToken());
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pill = (s, cls='') => `<span class="pill ${cls}">${esc(s)}</span>`;
const card = (title, body, extra='') => `<section class="card ${extra}"><h2>${title}</h2>${body}</section>`;
const btn = (label, action, cls='') => `<button class="button ${cls}" data-action="${action}">${label}</button>`;
const link = (label, target) => `<button class="text-button" data-go="${target}">${label} â†’</button>`;
const currentResult = () => {
  const patient = selectedPatient();
  if (state.backendConnected) {
    const saved = patient.latestAnalysis;
    if (!saved) return { score: null, threshold: null, cystMm: null, ductMm: null, profile: 'No MRI assessment recorded', evidence: [], date: null };
    return { ...saved, score: saved.score ?? null, threshold: saved.threshold ?? null,
      cystMm: saved.cystMm ?? null, ductMm: saved.ductMm ?? null, evidence: saved.evidence || [] };
  }
  if (state.analysis?.patientId === patient.id && state.analysis.result) return state.analysis.result;
  if (patient.latestAnalysis) return patient.latestAnalysis;
  return patient.id === 'CG-1031'
    ? {score:.38,threshold:.5,cystMm:22,ductMm:3,profile:'No / Low Risk Profile',evidence:['Cyst diameter measured at 22 mm','Main pancreatic duct measured at 3 mm']}
    : {score:.72,threshold:.5,cystMm:31,ductMm:4,profile:'Higher Risk Profile',evidence:['Cyst diameter measured at 31 mm','Main pancreatic duct measured at 4 mm']};
};
const activeAssessment = () => {const r=currentResult(),patient=selectedPatient();if(state.backendConnected){if(r.score==null)return '<div class="empty">No MRI assessment is stored for this patient.</div>';const high=String(r.riskClass||'').includes('HIGH');return `<div class="risk-summary ${high?'risk-high':'risk-low'}"><div class="risk-heading"><span class="risk-icon">${high?'!':'Â·'}</span><div><span class="eyebrow">AI EVIDENCE Â· CYST-X</span><h3>${esc(r.riskClass||'Assessment recorded')}</h3><p class="muted">Stored backend assessment</p></div><div class="score"><b>${Number(r.score).toFixed(2)}</b><small>AI model score</small></div></div><div class="meta"><span>Review threshold <b>${r.threshold==null?'Not recorded':Number(r.threshold).toFixed(2)}</b></span><span>Analysis date <b>${esc(r.date||patient.lastMri||'Not recorded')}</b></span></div><p class="muted">Model score is imaging evidence for clinical review, not a cancer probability.</p></div>`;}return RiskCard({score:r.score,threshold:r.threshold,riskClass:r.riskClass,date:r.date||patient.lastMri||'MRI pending'});};
const kyoto = () => {
  const high = ['Obstructive jaundice','Enhancing mural nodule â‰¥5 mm / solid component','MPD â‰¥10 mm','Suspicious/positive cytology'];
  const worry = ['Acute pancreatitis','Elevated CA19-9','New-onset / worsening diabetes','Cyst â‰¥30 mm','Enhancing mural nodule <5 mm','Thickened/enhancing cyst wall','MPD 5â€“9.9 mm','Abrupt duct caliber change + distal pancreatic atrophy','Lymphadenopathy','Cyst growth â‰¥2.5 mm/year'];
  return `<p class="muted">Kyoto 2024 guideline assessment Â· IPMN</p><div class="criteria"><h4>High-risk stigmata</h4>${high.map((x,i)=>criterion(x, i===0?'Absent':'Unknown')).join('')}<h4>Worrisome features</h4>${worry.map((x,i)=>criterion(x, i===3?'Present':i===8?'Absent':'Unknown')).join('')}</div>`;
};
function criterion(name, value) { value=state.kyoto[name]||(state.backendConnected?'Unknown':value); return `<div class="criterion"><span>${name}</span><select aria-label="${name}"><option ${value==='Unknown'?'selected':''}>Unknown</option><option ${value==='Present'?'selected':''}>Present</option><option ${value==='Absent'?'selected':''}>Absent</option></select></div>`; }
function legacyShell(content) {
  const role = state.role;
  const pendingCount=pendingAccess().length;
  const patientName=state.patient.name||'Patient';
  const initials=patientName.split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase();
  return `<div class="layout"><aside class="sidebar"><div class="brand"><span class="brand-mark">C</span><span>CystGuard<small>CARE MANAGEMENT</small></span></div><div class="workspace">${role==='doctor'?'CLINIC WORKSPACE':'PATIENT PORTAL'}</div><nav>${routes[role].map(p=>`<button class="nav-item ${page===p?'selected':''}" data-go="${p}"><span>${icon(p)}</span>${p}${role==='doctor'&&p==='Access Requests'&&pendingCount?`<b class="nav-badge">${pendingCount}</b>`:''}</button>`).join('')}</nav><div class="side-user"><div class="avatar">${role==='doctor'?'AR':esc(initials)}</div><div><b>${role==='doctor'?'Dr. A. Rivera':esc(patientName)}</b><small>${role==='doctor'?'Gastroenterology':'Patient'}</small></div><button class="logout" data-action="logout" title="Sign out">â†—</button></div></aside><main class="main"><header class="topbar"><div><span class="crumb">${role==='doctor'?'CLINIC':'MY CARE'}ã€€/ã€€</span><b>${page}</b></div><div class="top-right"><span class="live-dot"></span>Care plan up to date <div class="avatar small">${role==='doctor'?'AR':esc(initials)}</div></div></header><div class="content">${content}</div></main></div>`;
}
function icon(p) {
  const shapes = {
    Dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    Patients: '<circle cx="9" cy="8" r="3.5"/><path d="M2.8 20v-1.5a6.2 6.2 0 0 1 12.4 0V20zM16 5.2a3.5 3.5 0 0 1 0 6.6M18 14a5.5 5.5 0 0 1 3.2 5v1"/>',
    'Patient Profile': '<circle cx="12" cy="8" r="3.5"/><path d="M4 21a8 8 0 0 1 16 0M18 4h3M19.5 2.5v3"/>',
    'MRI Analysis': '<path d="M3 12h4l2.5-7 5 14 2.5-7h4"/>',
    Assessment: '<path d="M7 3h8l4 4v14H5V3z"/><path d="M14 3v5h5M8 12h8M8 16h8"/>',
    Timeline: '<path d="M3 12h4l2-5 4 10 2-5h6"/><circle cx="3" cy="12" r="1"/>',
    Surveillance: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    Reports: '<path d="M7 3h8l4 4v14H5V3z"/><path d="M14 3v5h5M8 12h8M8 16h8"/>',
    CareLoop: '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h6a4 4 0 0 1 0 8h-4a4 4 0 0 0 0 8h6"/>',
    Symptoms: '<path d="M20.8 8.8c0 5-8.8 11-8.8 11s-8.8-6-8.8-11A4.8 4.8 0 0 1 12 6a4.8 4.8 0 0 1 8.8 2.8z"/>',
    Medications: '<path d="M8 4a5 5 0 0 1 7 0l5 5a5 5 0 0 1-7 7l-5-5a5 5 0 0 1 0-7z"/><path d="m9 15 7-7"/>',
    Meals: '<path d="M3 12a9 9 0 1 0 18 0zM12 3v3M5 6l2 2M19 6l-2 2"/>',
    Nutrition: '<path d="M4 20V12h4v8M10 20V5h4v15M16 20v-9h4v9"/>',
    'Visit Preparation': '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M8 10h8M8 14h8M8 18h5"/>',
    Messages: '<path d="M4 5h16v12H9l-5 4z"/><path d="M8 10h8M8 13h5"/>',
    'Access Requests': '<path d="M4 5h16v14H4zM4 7l8 6 8-6"/>',
  };
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shapes[p] || shapes.Dashboard}</svg>`;
}
function shell(content) {
  const role=state.role, pendingCount=pendingAccess().length, patientName=state.patient.name||state.user?.display_name||'Patient';
  const name=role==='doctor'?(state.user?.display_name||state.user?.email?.split('@')[0]||'Clinician'):patientName;
  const initials=name.split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase();
  return `<div class="layout"><aside class="sidebar"><div class="brand"><span class="brand-mark">C</span><span>CystGuard<small>CONNECTED CARE</small></span></div><div class="workspace">${role==='doctor'?'CLINIC WORKSPACE':'PATIENT PORTAL'}</div><nav>${routes[role].map(item=>`<button class="nav-item ${page===item?'selected':''}" data-go="${item}"><span>${icon(item)}</span>${item}${role==='doctor'&&item==='Access Requests'&&pendingCount?`<b class="nav-badge">${pendingCount}</b>`:''}</button>`).join('')}</nav><div class="side-user"><div class="avatar">${esc(initials)}</div><div><b>${esc(name)}</b><small>${role==='doctor'?'Clinician':'Patient'}</small></div><button class="logout" data-action="logout" title="Sign out">Sign out</button></div></aside><main class="main"><header class="topbar"><div><span class="crumb">${role==='doctor'?'CLINIC':'MY CARE'} / </span><b>${page}</b></div><div class="top-right"><span class="live-dot"></span>${state.backendConnected?'Connected to care services':'Loading care workspace'}<div class="avatar small">${esc(initials)}</div><button class="button topbar-logout" data-action="logout">Sign out</button></div></header><div class="content">${state.apiError?`<div class="error" role="alert">${esc(state.apiError)}</div>`:''}${content}</div></main></div>`;
}
function header(title, subtitle, action='') { return `<div class="page-head"><div><p class="eyebrow">${state.role==='doctor'?'PATIENT CARE':'YOUR HEALTH JOURNEY'}</p><h1>${title}</h1><p class="muted">${subtitle}</p></div>${action}</div>`; }
function patientDashboard(){const r=currentResult(),request=[...state.accessRequests].reverse().find(x=>x.patientId===state.patient.id),lastMeal=state.meals[0];return `${header(`Good morning, ${esc(state.patient.name.split(' ')[0])}`,'A clear view of your care and next steps.',link('Open CareLoop','CareLoop'))}<div class="stats"><div class="stat"><small>CARE CONNECTION</small><b>${request?.status==='Approved'?'Connected':request?.status==='Pending'?'Awaiting approval':'Not connected'}</b><span>${request?.status==='Approved'?'Dr. A. Rivera Â· Gastroenterology':'Your clinician reviews access requests'}</span></div><div class="stat"><small>LATEST MRI</small><b>${esc(state.patient.lastMri||'Not recorded')}</b><span>${esc(state.patient.diagnosis)}</span></div><div class="stat"><small>NEXT FOLLOW-UP</small><b>${esc(state.patient.nextVisit||'To be scheduled')}</b><span>MRI and care review</span></div><div class="stat"><small>CARE STATUS</small><b>${pill(state.reviewed?'Clinician reviewed':request?.status==='Pending'?'Request pending':'In care',state.reviewed?'green':request?.status==='Pending'?'amber':'blue')}</b><span>Care team led review</span></div></div><div class="dashboard-grid">${card('Latest assessment',`${activeAssessment()}${link('View assessment','Assessment')}`)}${card('Upcoming care',`<div class="upcoming-panel"><div class="calendar-tile"><b>${esc((state.patient.nextVisit||'14 Dec 2026').slice(0,2))}</b><small>DEC</small></div><div><b>MRI follow-up and care review</b><p class="muted">${esc(state.patient.nextVisit||'14 Dec 2026')} Â· Care team visit</p></div></div><div class="dashboard-card-footer">${link('Prepare for visit','Visit Preparation')} ${link('View surveillance','Surveillance')}</div>`)}</div><div class="grid two">${card('Recent symptoms',state.symptoms.length?`${state.symptoms.slice(0,2).map(s=>`<div class="patient-row"><div class="grow"><b>${esc(s.name)}</b><small>${esc(s.date)} Â· ${esc(s.note||'No additional notes')}</small></div>${pill(s.severity,s.severity==='Severe'?'red':'blue')}</div>`).join('')}${link('Track symptoms','Symptoms')}`:`<div class="empty">No symptom entries yet.</div>${link('Add a symptom','Symptoms')}`)}${card('Recent meal',lastMeal?`<div class="patient-row"><div class="grow"><b>${esc(lastMeal.name)}</b><small>${esc(lastMeal.date)} Â· ~${lastMeal.kcal} kcal${lastMeal.protein?` Â· ${lastMeal.protein} g protein`:''}</small></div>${pill(lastMeal.confirmed?'Confirmed':'Estimate','green')}</div>${link('Open meal history','Meals')}`:`<div class="empty">No meal entries yet.</div>${link('Add a meal','Meals')}`)}</div>`;}
function doctorHome(){const pending=pendingAccess();const approved=state.accessRequests.filter(r=>r.status==='Approved');const featured=approved[0];return `${header('Good morning, Dr. Rivera','Your clinic workspace, requests, and approved patient care.',link('Review access requests','Access Requests'))}<div class="stats"><div class="stat stat-action"><small>ACCESS REQUESTS</small><b>${pending.length} awaiting review</b><span>Patient records stay closed until you approve.</span>${link('Open request inbox','Access Requests')}</div><div class="stat"><small>CONNECTED PATIENTS</small><b>${approved.length}</b><span>Approved care connections</span></div><div class="stat stat-code"><small>YOUR CLINICIAN CODE</small><b>${esc(state.doctorAccessCode)}</b><span>Share with patients to receive their request.</span></div><div class="stat"><small>CARE WORKFLOW</small><b>Clinician led</b><span>Review each assessment before sharing.</span></div></div><div class="dashboard-grid">${card(`Access requests ${pending.length?`<span class="inline-count">${pending.length}</span>`:''}`,pending.length?`<div class="access-dashboard-list">${state.accessRequests.map((r,i)=>r.status==='Pending'?AccessRequestCard({request:r,index:i,controls:true}):'').join('')}</div><div class="dashboard-card-footer">${link('View all requests','Access Requests')}</div>`:`<div class="empty-access"><div class="empty-icon">âœ“</div><b>No requests to review</b><p>When a patient registers with your clinician code, their request will appear here.</p><span class="code-inline">${esc(state.doctorAccessCode)}</span></div>`)}${card('Approved patient workspace',featured?`<div class="patient-row"><div class="avatar">${esc(featured.name.split(/\s+/).map(x=>x[0]).join('').slice(0,2))}</div><div class="grow"><b>${esc(featured.name)}</b><small>${esc(featured.patientId)} Â· Access approved</small></div><button class="button" data-open-patient="${esc(featured.patientId)}">Open profile</button></div><div class="dashboard-card-footer"><button class="text-button" data-open-patient="${esc(featured.patientId)}">Continue to MRI analysis â†’</button></div>`:`<div class="empty">Patient information becomes available here after you approve their request.</div>`)}</div>`;}
function patients() {
  const people = state.patientDirectory;
  const connected = people.filter(person => patientHasApprovedAccess(person.id)).length;
  const pending = people.filter(person => state.accessRequests.some(request => request.patientId === person.id && request.status === 'Pending')).length;
  const form = state.addPatientOpen ? `<form id="doctor-add-patient-form" class="add-patient-form"><div class="form-grid"><label>Patient name<input name="name" required maxlength="100" placeholder="Full name"></label><label>Email address<input name="email" type="email" required maxlength="254" placeholder="name@example.com"></label><label>Age <span class="muted">(optional)</span><input name="age" type="number" min="0" max="120" placeholder="Age"></label><label>Care note <span class="muted">(optional)</span><input name="diagnosis" maxlength="160" placeholder="Brief care context"></label></div><p class="invite-note">The patient is added to your roster. Their clinical information stays locked until they register, request access, and you approve it.</p><div class="actions"><button class="button primary" type="submit">Add patient</button><button class="button" type="button" data-action="toggle-add-patient">Cancel</button></div><p id="patient-form-error" class="error hidden"></p></form>` : '';
  const rows = people.map(person => {
    const request = [...state.accessRequests].reverse().find(item => item.patientId === person.id);
    const approved = request?.status === 'Approved';
    const pendingRequest = request?.status === 'Pending';
    const status = approved ? 'Connected' : pendingRequest ? 'Approval pending' : request?.status === 'Declined' ? 'Request declined' : 'No request yet';
    const initials = person.name.split(/\s+/).map(part => part[0]).join('').slice(0,2).toUpperCase();
    return `<div class="patient-record-row"><div class="avatar">${esc(initials)}</div><div class="patient-record-main"><b>${esc(person.name)}</b><small>${esc(person.id)} Â· ${esc(person.email||'Email not provided')}</small></div><div class="patient-record-meta"><span class="eyebrow">CARE ACCESS</span>${pill(status,approved?'green':pendingRequest?'amber':'blue')}</div><div class="patient-record-meta"><span class="eyebrow">LATEST MRI</span><b>${esc(person.lastMri||'Not recorded')}</b></div><div class="patient-row-action">${approved?`<button class="button" data-open-patient="${esc(person.id)}">View profile <span aria-hidden="true">â†’</span></button>`:pendingRequest?`<button class="text-button" data-go="Access Requests">Review request â†’</button>`:`<span class="muted">Waiting for patient</span>`}</div></div>`;
  }).join('');
  return `${header('Patients','A clear roster for invitations, access approvals, and connected care.',`<button class="button primary" data-action="toggle-add-patient">ï¼‹ Add patient</button>`)}<div class="directory-summary"><div><span class="eyebrow">PATIENT DIRECTORY</span><b>${people.length}</b><small>people in your workspace</small></div><div><span class="eyebrow">CONNECTED</span><b>${connected}</b><small>approved care connections</small></div><div><span class="eyebrow">AWAITING APPROVAL</span><b>${pending}</b><small>requests to review</small></div><div class="directory-mark">Care access is patient-approved and clinician-reviewed</div></div>${form}${card('Patient directory',people.length?`<div class="patient-directory">${rows}</div>`:`<div class="empty-access"><div class="empty-icon">ï¼‹</div><b>Your patient list starts here</b><p>Add a patient to prepare an invitation. Their clinical record will open only after an access request is approved.</p><button class="button primary" data-action="toggle-add-patient">Add your first patient</button></div>`)}`;
}
function pendingAccess() { return state.accessRequests.filter(r=>r.status==='Pending'); }
function accessRequests() { const rows=state.accessRequests.length?state.accessRequests.map((request,index)=>AccessRequestCard({request,index,controls:true})).join(''):'<div class="empty-access"><div class="empty-icon">âœ‰</div><b>No patient requests yet</b><p>Share your clinician code. New requests will arrive here for approval.</p></div>';return `${header('Access requests','Review and approve patient connections before opening their clinical workspace.')}${card('Request inbox',`<div class="code-panel"><div><span class="eyebrow">YOUR CLINICIAN CODE</span><b>${esc(state.doctorAccessCode)}</b><small>Patients enter this code during registration.</small></div><span class="pill ${pendingAccess().length?'amber':'green'}">${pendingAccess().length} pending</span></div><div class="access-list">${rows}</div>`)}`; }
function careTeamAccess() {
  const request=[...state.accessRequests].reverse().find(r=>r.patientId===state.patient.id);
  const requestBody=request
    ? `<div class="request-status"><div class="request-icon">${request.status==='Approved'?'âœ“':'Â·Â·Â·'}</div><div><span class="eyebrow">REQUEST ${esc(request.reference)}</span><h3>${request.status==='Approved'?'Access approved':request.status==='Declined'?'Request declined':'Waiting for clinician approval'}</h3><p class="muted">${request.status==='Approved'?'Dr. A. Rivera can now access your CystGuard care workspace.':request.status==='Declined'?'Your care team declined this request. Contact the clinic if you need help.':'Your request has been sent to Dr. A. Rivera. You will see access here after approval.'}</p></div>${pill(request.status,request.status==='Approved'?'green':request.status==='Pending'?'amber':'red')}</div>`
    : `<form id="access-form" class="access-form"><label>Clinician access code<input name="code" required autocomplete="off" placeholder="For example, CG-AR-2486"></label><div class="access-clinician"><div class="avatar">AR</div><div><b>Dr. A. Rivera</b><small>Gastroenterology Â· Pancreatic care</small></div></div><button class="button primary">Send access request</button><p id="access-error" class="error hidden"></p></form>`;
  return `${header('Connect to your care team','Enter the access code provided by your clinician. Your records remain private until the clinician approves your request.')}${card('Request clinician access',requestBody)}${card('How access works',`<div class="access-steps"><div><i>1</i><span><b>Enter your clinician code</b><small>Use the code shared by your care team.</small></span></div><div><i>2</i><span><b>Clinician reviews your request</b><small>Your care team confirms the connection.</small></span></div><div><i>3</i><span><b>Access is granted after approval</b><small>You can see the connection status here.</small></span></div></div>`)}`;
}
function profile() { const patient=selectedPatient(); if(!patientHasApprovedAccess(patient.id)) return `${header('Patient profile','Patient details are protected until this patientâ€™s care access is approved.')}${card('Access required',`<div class="empty">${esc(patient.name)} has not approved access for this workspace yet. Review their request before opening clinical information.</div>${link('Review access requests','Access Requests')}`)}`; const initials=patient.name.split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase(); const result=currentResult(); const recentSymptoms=patient.symptoms||[],recentMeals=patient.meals||[]; return `${header('Patient profile','Care overview and linked clinical workflow.',btn('Open MRI analysis','mri','primary'))}<div class="profile-banner"><div class="avatar large">${esc(initials)}</div><div class="grow"><h2>${esc(patient.name)}</h2><p>${esc(patient.id)} Â· ${patient.age?`${esc(patient.age)} years Â· `:''}${esc(patient.diagnosis||'Care profile')}</p></div>${pill('Access approved','green')}</div><div class="grid two">${card('Patient information',`<div class="meta vertical"><span>Email <b>${esc(patient.email||'Not provided')}</b></span><span>Most recent MRI <b>${esc(patient.lastMri||'Not recorded')}</b></span><span>Follow-up due <b>${esc(patient.nextVisit||'To be scheduled')}</b></span><span>Care team <b>Dr. A. Rivera</b></span></div>`)}${card('Latest assessment',activeAssessment()+`<p class="muted">${esc(result.profile)} Â· Imaging evidence for clinician review.</p>`+link('Review assessment','Assessment'))}${card('Recent patient updates',`${recentSymptoms.length?`<div class="patient-row"><div class="grow"><b>${esc(recentSymptoms[0].name)}</b><small>Symptom Â· ${esc(recentSymptoms[0].date)} Â· ${esc(recentSymptoms[0].severity)}</small></div></div>`:'<p class="muted">No symptom updates recorded.</p>'}${recentMeals.length?`<div class="patient-row"><div class="grow"><b>${esc(recentMeals[0].name)}</b><small>Meal Â· ${esc(recentMeals[0].date)}</small></div></div>`:'<p class="muted">No meal updates recorded.</p>'}`)}${card('Care pathway',`<div class="path">${['MRI analysis','Guideline review','Clinician review','Surveillance plan','Clinical report'].map((x,i)=>`<div class="path-item"><span>${i+1}</span><div><b>${x}</b><small>${i<2?'Available to review':'Next in workflow'}</small></div></div>`).join('')}</div>`)}</div>`; }
const analysisStages=['File validation','MRI preprocessing','Cyst-X model inference','Evidence and concordance'];
function analysisProgress(){return AnalysisProgress({analysis:state.analysis,stages:analysisStages});}
function mri(){return DoctorMRIAnalysis({result:state.latestStudy||null,busy:state.analysis?.status==='running'});}
const highRiskItems=['Obstructive jaundice','Enhancing mural nodule â‰¥5 mm / solid component','MPD â‰¥10 mm','Suspicious/positive cytology'];
const worrisomeItems=['Acute pancreatitis','Elevated CA19-9','New-onset / worsening diabetes','Cyst â‰¥30 mm','Enhancing mural nodule <5 mm','Thickened/enhancing cyst wall','MPD 5â€“9.9 mm','Abrupt duct caliber change + distal pancreatic atrophy','Lymphadenopathy','Cyst growth â‰¥2.5 mm/year'];
function findingStatus(name){if(state.kyoto[name])return state.kyoto[name];if(state.backendConnected)return 'Unknown';if(name==='Obstructive jaundice'||name==='Lymphadenopathy')return 'Absent';const r=currentResult();if(name==='Cyst â‰¥30 mm')return r.cystMm>=30?'Present':'Absent';if(name==='MPD 5â€“9.9 mm')return r.ductMm>=5&&r.ductMm<10?'Present':'Absent';return 'Unknown';}
function guidelineSummary(){const present=[...highRiskItems,...worrisomeItems].filter(x=>findingStatus(x)==='Present');const unknown=[...highRiskItems,...worrisomeItems].filter(x=>findingStatus(x)==='Unknown');return {present,unknown};}
function concordance(){const r=currentResult(),aiHigh=r.score>=r.threshold,g=guidelineSummary();if(g.present.length&&aiHigh)return {label:'Concordant â€” Higher Risk',tone:'amber',detail:`AI evidence is above the review threshold. Guideline features recorded as present: ${g.present.join('; ')}.`};if(g.present.length&&!aiHigh)return {label:'Discordant',tone:'amber',detail:'Guideline features are recorded as present while the AI model score is below its review threshold.'};if(g.unknown.length)return {label:'Review Required',tone:'blue',detail:'Some guideline findings remain unknown. Complete the clinical assessment before interpreting agreement.'};return aiHigh?{label:'Discordant',tone:'amber',detail:'AI evidence is above the review threshold while recorded guideline features are absent.'}:{label:'Concordant â€” Lower Risk',tone:'green',detail:'AI evidence is below the review threshold and recorded guideline features are absent.'};}
function assessment(){const r=currentResult(),g=guidelineSummary(),c=concordance(),delta=Math.abs(r.score-r.threshold).toFixed(2);return `${header('MRI assessment','Follow the evidence from model output through clinician review.',link('View timeline','Timeline'))}<div class="workflow-banner"><div class="workflow-track">${['MRI received','Model analysis','Guideline comparison','Clinician review'].map((x,i)=>`<div class="workflow-node ${i<3?'finished':state.reviewed?'finished':'current'}"><i>${i<3||state.reviewed?'âœ“':i+1}</i><span>${x}</span></div>`).join('')}</div></div><div class="grid two">${card('1 Â· AI evidence',activeAssessment()+`<div class="reasoning"><h3>Model reasoning</h3><p>Model score <b>${r.score.toFixed(2)}</b> is ${r.score>=r.threshold?'above':'below'} the review threshold of <b>${r.threshold.toFixed(2)}</b> by ${delta}. This is imaging evidence for clinician review, not a cancer probability.</p><div class="evidence-list"><b>Evidence summary</b><span>â€¢ MRI sequence: T1</span><span>â€¢ Measured cyst diameter: ${r.cystMm} mm</span><span>â€¢ Measured main pancreatic duct: ${r.ductMm} mm</span><span>â€¢ Model: Cyst-X Â· 3D DenseNet-121</span></div></div>`)}${card('2 Â· Kyoto 2024 guideline assessment',`<p class="muted">Clinical findings are recorded separately from AI evidence.</p>${kyoto()}<div class="evidence-list"><b>Present findings</b>${g.present.length?g.present.map(x=>`<span>â€¢ ${esc(x)}</span>`).join(''):'<span>No findings currently recorded as present.</span>'}</div>`)}</div><div class="grid two">${card('3 Â· AI and guideline concordance',`<div class="concordance-result">${pill(c.label,c.tone)}<p>${esc(c.detail)}</p></div><div class="separation"><div><span class="eyebrow">AI EVIDENCE</span><b>${esc(r.profile)}</b><small>AI model score ${r.score.toFixed(2)} Â· threshold ${r.threshold.toFixed(2)}</small></div><div><span class="eyebrow">GUIDELINE ASSESSMENT</span><b>${g.present.length?`${g.present.length} present finding${g.present.length===1?'':'s'}`:'No present findings'}</b><small>${g.unknown.length} unknown finding${g.unknown.length===1?'':'s'} require context</small></div></div>`)}${card('4 Â· Trust and uncertainty',`<div class="meta vertical"><span>Trust status <b>${pill('Review required','amber')}</b></span><span>Data completeness <b>82%</b></span><span>Uncertainty state <b>Moderate Â· clinical review</b></span><span>Calibration <b>Not calibrated</b></span><span>Review requirement <b>Clinician review required</b></span></div><p class="muted">No calibrated probability is available for this result.</p>`)}</div>${card('5 Â· Clinician review',`<p class="muted">Record your interpretation after reviewing AI evidence, guideline findings, concordance, and uncertainty.</p><div class="grid two"><label>Clinician assessment<select id="clinician-assessment"><option value="">Select assessment</option><option>Continue surveillance</option><option>Discuss at multidisciplinary review</option><option>Additional clinical evaluation</option></select></label><label>Clinical notes<textarea id="clinical-notes" rows="4" placeholder="Add clinical context and review notes">${esc(state.notes)}</textarea></label></div><div class="actions">${btn(state.reviewed?'Assessment reviewed':'Mark as reviewed','review','primary')} ${link('Plan surveillance','Surveillance')} ${link('View report','Reports')}</div>`)}`;}
function timeline() { const r=currentResult(),mriDate=r.date||state.patient.lastMri||'18 Sep 2026';return `${header('Longitudinal timeline',`Imaging and surveillance history for ${esc(state.patient.name)}.`)}${card('MRI assessment history',`<div class="chart"><div class="chart-bar"><span>Sep 2025</span><i style="height:39%"></i><b>0.39</b></div><div class="chart-bar"><span>Mar 2026</span><i style="height:54%"></i><b>0.54</b></div><div class="chart-bar current"><span>${esc(mriDate)}</span><i style="height:${Math.max(5,r.score*100)}%"></i><b>${r.score.toFixed(2)}</b></div><div class="chart-label">AI model score trend Â· model scores are not cancer probabilities</div></div><div class="timeline-entry"><span class="timeline-dot"></span><div><small>${esc(mriDate.toUpperCase())} Â· CURRENT</small><h3>${esc(r.profile)} ${pill(state.reviewed?'Reviewed':'Review required',state.reviewed?'green':'amber')}</h3><p>AI model score ${r.score.toFixed(2)} Â· Cyst ${r.cystMm} mm Â· MPD ${r.ductMm} mm</p><p class="muted">Surveillance: follow-up planned for ${esc(state.patient.nextVisit||'14 Dec 2026')}</p></div></div><div class="timeline-entry"><span class="timeline-dot"></span><div><small>20 MAR 2026</small><h3>No / Low Risk Profile ${pill('Reviewed','green')}</h3><p>AI model score 0.54 Â· Cyst 28 mm Â· No high-risk stigmata recorded</p><p class="muted">Surveillance visit completed 21 Mar 2026</p></div></div><div class="timeline-entry"><span class="timeline-dot"></span><div><small>22 SEP 2025</small><h3>No / Low Risk Profile ${pill('Reviewed','green')}</h3><p>AI model score 0.39 Â· Cyst 26 mm Â· Surveillance established</p></div></div>`)}`; }
function surveillance() { return `${header('Surveillance','Plan and track upcoming follow-ups.')}${card('Add follow-up',`<form id="followup-form" class="form-row"><label>Target date<input name="date" type="date" required value="2026-12-14"></label><label>Reason<input name="reason" required value="MRI follow-up and care review"></label><button class="button primary">Add follow-up</button></form>`)}${card('Surveillance history',`<div class="table"><div class="tr th"><span>Target date</span><span>Reason</span><span>Status</span><span>Action</span></div>${state.followups.map((f,i)=>`<div class="tr"><span>${esc(f.date)}</span><span>${esc(f.reason)}</span><span>${pill(f.status,f.status==='Completed'?'green':'blue')}</span><span>${f.status!=='Completed'?`<button class="text-button" data-complete="${i}">Mark completed</button>`:''}</span></div>`).join('')}<div class="tr"><span>21 Mar 2026</span><span>Surveillance MRI review</span>${pill('Completed','green')}<span>â€”</span></div></div>`)}`; }
function reports() { const r=currentResult(),g=guidelineSummary(),c=concordance();return `${header('Clinical report','Review and print the clinical summary.',`<button class="button primary" onclick="window.print()">Print report</button>`)}<article class="report">${card('CystGuard Â· Clinical MRI Review',`<div class="report-head"><div><p class="eyebrow">PATIENT</p><h2>${esc(state.patient.name)}</h2><p>${esc(state.patient.id)} Â· ${state.patient.age} years Â· ${esc(state.patient.diagnosis)}</p></div><div><p class="eyebrow">MRI DATE</p><h3>${esc(r.date||state.patient.lastMri||'MRI pending')}</h3><p>T1 MRI Â· Cyst-X Â· 3D DenseNet-121</p></div></div><hr><h3>AI evidence</h3>${activeAssessment()}<h3>Reasoning summary</h3><p>${esc(r.profile)} Â· model score ${r.score.toFixed(2)} against threshold ${r.threshold.toFixed(2)}. Cyst ${r.cystMm} mm; MPD ${r.ductMm} mm. The model score is imaging evidence, not a cancer probability.</p><h3>Kyoto 2024 guideline assessment</h3><p>${g.present.length?`Present findings: ${g.present.map(esc).join('; ')}.`:'No findings are recorded as present.'} ${g.unknown.length} finding(s) remain unknown. Assessment requires clinician interpretation.</p><h3>AI and guideline concordance</h3><p>${esc(c.label)} Â· ${esc(c.detail)}</p><h3>Trust and uncertainty</h3><p>Calibration: Not calibrated. Data completeness: 82%. Clinician review required.</p><h3>Longitudinal findings</h3><p>Current cyst measurement: ${r.cystMm} mm. Current MPD: ${r.ductMm} mm. Historical MRI records remain available in the timeline.</p><h3>Clinician assessment</h3><p>${esc(state.assessment||'Pending clinician review')}</p><p>${esc(state.notes||'No clinical notes recorded.')}</p><h3>Surveillance plan</h3>${state.followups.map(f=>`<p>${esc(f.date)} Â· ${esc(f.reason)} Â· ${esc(f.status)}</p>`).join('')}`,'report-card')}</article><p class="fine-print">This report summarizes recorded imaging evidence and clinician-entered information. It does not replace clinical judgment.</p>`; }
function symptoms() { return `${header('Symptoms','Track how you are feeling between visits.')}${card('Add symptom',`<form id="symptom-form" class="form-row"><label>Symptom<input name="name" required placeholder="Describe a symptom"></label><label>Severity<select name="severity"><option>Mild</option><option>Moderate</option><option>Severe</option></select></label><label>Date<input name="date" type="date" required value="${new Date().toISOString().slice(0,10)}"></label><label>Notes<input name="note" placeholder="Optional details"></label><button class="button primary">Save symptom</button></form>`)}${card('Symptom history',state.symptoms.length?`<div class="table"><div class="tr th"><span>Symptom</span><span>Severity</span><span>Date</span><span>Notes</span></div>${state.symptoms.map(s=>`<div class="tr"><b>${esc(s.name)}</b>${pill(s.severity,s.severity==='Severe'?'red':'blue')}<span>${esc(s.date)}</span><span>${esc(s.note||'â€”')}</span></div>`).join('')}</div>`:`<div class="empty">No symptoms recorded yet.</div>`)}`; }
function medications() { return `${header('Medications','Your current medication list and verification status.')}${card('Medication list',`<div class="table"><div class="tr th"><span>Medication</span><span>Dose and frequency</span><span>Route Â· dates</span><span>Verification</span></div><div class="tr"><span><b>Omeprazole</b><small>Generic: omeprazole</small></span><span>20 mg Â· Once daily</span><span>Oral Â· 01 Jun 2026 â€“ ongoing</span>${pill('Verified','green')}</div><div class="tr"><span><b>Vitamin D3</b><small>Generic: cholecalciferol</small></span><span>1000 IU Â· Once daily</span><span>Oral Â· 10 Jan 2026 â€“ ongoing</span>${pill('Patient reported','amber')}</div></div><div class="divider"></div><p class="muted">For medication changes, please consult your care team.</p><label class="button">Add medication document<input type="file" hidden accept=".pdf,.jpg,.jpeg,.png"></label>`)}`; }
function estimateMarkup(estimate){return `<b>Estimated nutrition</b><span>~${estimate.kcal} kcal Â· Protein ~${estimate.protein} g Â· Carbohydrates ~${estimate.carbs} g Â· Fat ~${estimate.fat} g</span><small>${esc(estimate.label)} Â· Values remain estimates until you confirm the meal.</small>`;}
function refreshMealEstimate(){const description=document.getElementById('meal-description')?.value||'',imageName=document.getElementById('meal-photo')?.files?.[0]?.name||'',box=document.getElementById('meal-estimate');if(box)box.innerHTML=estimateMarkup(estimateMeal(description,imageName,state.meals.length));}
function meals() { const estimate=estimateMeal('', '', state.meals.length);return `${header('Meals & nutrition','Record meals and review nutrition estimates.')}${card('Add a meal',`<form id="meal-form"><label>Meal photo<input id="meal-photo" name="image" type="file" accept="image/*"></label><label>Meal description<input id="meal-description" name="name" required placeholder="Describe the food in your meal"></label><div class="estimate-box" id="meal-estimate">${estimateMarkup(estimate)}</div><label class="check"><input name="confirm" type="checkbox"> I confirm these food items describe my meal</label><button class="button primary">Save meal entry</button></form>`)}${card('Meal history',`<div class="table"><div class="tr th"><span>Meal</span><span>Date</span><span>Nutrition estimate</span><span>Status</span></div>${state.meals.map(m=>`<div class="tr"><b>${esc(m.name)}</b><span>${esc(m.date)}</span><span>~${m.kcal} kcal${m.protein?` Â· ${m.protein} g protein`:''}</span>${pill(m.confirmed?'Patient confirmed':'Estimate Â· unconfirmed',m.confirmed?'green':'amber')}</div>`).join('')}</div>`)}`; }
function nutrition() { return `${header('Nutrition timeline','Food entries and patient-confirmed nutrition estimates.')}${card('Recent nutrition',`<div class="chart nutrition-bars">${state.meals.map((m,i)=>`<div class="chart-bar"><span>${esc(m.date)}</span><i style="height:${Math.min(90,m.kcal/5)}%"></i><b>~${m.kcal} kcal</b></div>`).join('')}</div><p class="muted">Values are estimates until you confirm each meal. Nutrition information is not a substitute for advice from your care team.</p>${link('Record a meal','Meals')}`)}`; }
function visit() { const r=currentResult();return `${header('Visit preparation','Bring a clear overview to your next care review.')}${card('Your visit summary',`<div class="grid two"><div><p class="eyebrow">RECENT SYMPTOMS</p>${state.symptoms.map(s=>`<p>${esc(s.date)} Â· ${esc(s.name)} (${esc(s.severity)})</p>`).join('')||'<p>None recorded</p>'}<p class="eyebrow">MEDICATIONS</p><p>Omeprazole 20 mg daily Â· Vitamin D3 1000 IU daily</p><p class="eyebrow">LATEST MRI ASSESSMENT</p><p>${esc(r.date||state.patient.lastMri||'No MRI recorded')} Â· ${esc(r.profile)} Â· clinician review</p><p class="eyebrow">SURVEILLANCE</p><p>Next follow-up Â· ${esc(state.patient.nextVisit||'To be scheduled')}</p></div><div><p class="eyebrow">QUESTIONS FOR YOUR DOCTOR</p>${state.questions.map((q,i)=>`<div class="question">${esc(q)}<button class="remove" data-remove-question="${i}">Ã—</button></div>`).join('')}<form id="question-form" class="form-row"><label>Add a question<input name="question" required placeholder="What would you like to discuss?"></label><button class="button">Add question</button></form></div></div>`)}`; }
function messages() { return `${header('Messages','Secure care team conversation.')}${card('Maya Patel â†” Dr. A. Rivera',`<div class="thread">${state.messages.map(m=>`<div class="message ${m.from==='patient'?'mine':''}"><p>${esc(m.text)}</p><small>${esc(m.time)}</small></div>`).join('')}</div><form id="message-form" class="form-row"><label>Message<input name="text" required placeholder="Write a message to your care team"></label><button class="button primary">Send message</button></form><p class="muted">For urgent medical concerns, contact your local emergency service or care team by phone.</p>`)}`; }
function patientCareloop() { const r=currentResult(),request=[...state.accessRequests].reverse().find(x=>x.patientId===state.patient.id);return `${header('Your CareLoop','A connected view of your ongoing care.')}${card('Your care journey',`<div class="careloop">${[['Assessment',`MRI assessment Â· ${r.date||state.patient.lastMri||'latest review'}`,'Assessment'],['Care team access',request?.status==='Approved'?'Connection approved':request?.status==='Pending'?'Waiting for clinician approval':'Connect with your clinician','Care Team Access'],['Doctor review',state.reviewed?'Reviewed by your care team':'Care team review required','Assessment'],['Surveillance',`Next follow-up ${state.patient.nextVisit||'to be scheduled'}`,'Surveillance'],['Symptoms',`${state.symptoms.length} recent symptom entries`,'Symptoms'],['Medication tracking','2 medicines in your list','Medications'],['Meal tracking',`${state.meals.length} recent meal entries`,'Meals'],['Visit preparation','Add questions for your next visit','Visit Preparation'],['Next review','MRI follow-up and care review','Surveillance']].map((x,i)=>`<button class="journey" data-go="${x[2]}"><span class="journey-no">${String(i+1).padStart(2,'0')}</span><span class="grow"><b>${x[0]}</b><small>${x[1]}</small></span><span>â†’</span></button>`).join('')}</div>`)}`; }
function pageContent() { if(state.role==='doctor'&&['MRI Analysis','Assessment','Timeline','Surveillance','Reports','Messages'].includes(page)&&!patientHasApprovedAccess(state.selectedPatientId))return `${header(page,'Clinical information is available after this patient approves access.')}${card('Access approval required',`<div class="empty">Approve ${esc(selectedPatient().name)}â€™s access request before opening clinical information.</div>${link('Review access requests','Access Requests')}`)}`;switch(page) { case 'Dashboard':return state.role==='doctor'?doctorHome():patientDashboard();case 'Patients':return patients();case 'Access Requests':return accessRequests();case 'Care Team Access':return careTeamAccess();case 'Patient Profile':return profile();case 'MRI Analysis':return mri();case 'Assessment':return assessment();case 'Timeline':return timeline();case 'Surveillance':return surveillance();case 'Reports':return reports();case 'CareLoop':return patientCareloop();case 'Symptoms':return symptoms();case 'Medications':return medications();case 'Meals':return meals();case 'Nutrition':return nutrition();case 'Visit Preparation':return visit();case 'Messages':return messages();default:return dashboard();} }
function legacyAuthPage(){return '';}
function authPage(){const clinician=authRole==='doctor',register=authMode==='register';return `<div class="auth-layout"><section class="auth-aside"><div class="brand"><span class="brand-mark">C</span><span>CystGuard<small>CONNECTED PANCREATIC CARE</small></span></div><div class="auth-message"><span class="eyebrow">CARE THAT STAYS CONNECTED</span><h1>One place for your care journey.</h1><p>Sign in securely to view your own records. Patient care tabs are available before connecting a clinician.</p><div class="auth-points"><span>âœ“ Your records stay yours</span><span>âœ“ Request clinician access when ready</span><span>âœ“ Connected data is saved to your account</span></div></div><small class="auth-foot">CystGuard Â· Pancreatic care coordination</small></section><main class="auth-main"><div class="auth-card"><div class="auth-switch"><button class="${!clinician?'active':''}" data-auth-role="patient">Patient</button><button class="${clinician?'active':''}" data-auth-role="doctor">Clinician</button></div><p class="eyebrow">${clinician?'CLINICIAN WORKSPACE':'PATIENT PORTAL'}</p><h2>${register?'Create your account':clinician?'Welcome back':'Welcome to your care space'}</h2><p class="muted">${register?'Your account and patient data are stored by the CystGuard service.':clinician?'Sign in to review patient requests and connected care.':'Sign in or create an account to access your care tabs.'}</p><div class="auth-tabs"><button class="${!register?'active':''}" data-auth-mode="login">Sign in</button><button class="${register?'active':''}" data-auth-mode="register">Create account</button></div>${register?`<form id="auth-register-form"><label>Full name<input name="name" required maxlength="120" autocomplete="name" placeholder="Your name"></label><label>Email address<input type="email" name="email" required autocomplete="email" placeholder="you@example.com"></label><label>Create password<input type="password" name="password" required minlength="10" autocomplete="new-password" placeholder="At least 10 characters"></label>${clinician?'':`<div class="access-code-field"><label>Clinician access code <span class="muted">(optional)</span><input name="code" autocomplete="off" placeholder="Enter the code from your clinician"></label><small>You can request access later from Care Team Access. Your care tabs are available now.</small></div>`}<button class="button primary auth-submit">Create ${clinician?'clinician':'patient'} account</button><p id="auth-error" class="error hidden"></p></form>`:`<form id="role-login-form"><label>Email address<input type="email" name="email" required autocomplete="email" placeholder="you@example.com"></label><label>Password<input type="password" name="password" required autocomplete="current-password" placeholder="Enter your password"></label><button class="button primary auth-submit">Sign in to ${clinician?'clinician workspace':'patient portal'}</button><p id="auth-error" class="error hidden"></p></form>`}<div class="auth-help">${clinician?'Clinician account required.':'Your clinician can share an access code after account creation.'}</div></div></main></div>`;}
function backendPatientDashboard(){const next=state.followups.find(item=>!['COMPLETED','Completed','CANCELLED'].includes(item.status));const connection=state.accessRequests.at(-1);return PatientDashboard({name:state.patient.name,connection:connection?.status||'Not connected',nextFollowup:next?.date,latestMRI:state.latestProfile?.latest_mri?.study_date,assessmentAvailable:Boolean(state.latestProfile?.latest_assessment),symptoms:state.symptoms.map(item=>({name:item.name,date:item.date,severity:item.severityLabel||'Not recorded'})),medicationCount:state.medicationRecords?.length||0,mealCount:state.meals.length});}
function backendDoctorHome(){const nutritionAlerts=(state.doctorOverview||[]).flatMap(({patient,nutrition})=>(nutrition?.alerts||[]).map(alert=>({patientId:Number(patient.id),patientName:patient.name,...alert})));return DoctorDashboard({name:state.user?.display_name||'Clinician',accessCode:state.doctorAccessCode,requests:state.accessRequests.filter(item=>item.status==='Pending'),overview:state.doctorOverview||[],nutritionAlerts});}
function backendPatients(){const form=state.addPatientOpen?`<form id="doctor-add-patient-form" class="add-patient-form"><div class="form-grid"><label>Registered patient email<input name="email" type="email" required placeholder="patient@example.com"></label></div><p class="invite-note">This creates a pending access request for an existing patient account. The patient must have registered first.</p><div class="actions"><button class="button primary">Add patient request</button><button class="button" type="button" data-action="toggle-add-patient">Cancel</button></div><p id="patient-form-error" class="error hidden"></p></form>`:'';const active=state.patientDirectory;return `${header('Patients','Only database accounts with active access approval appear in this directory.',`<button class="button primary" data-action="toggle-add-patient">ï¼‹ Add patient</button>`)}<div class="directory-summary"><div><span class="eyebrow">CONNECTED</span><b>${active.length}</b><small>active relationships</small></div><div><span class="eyebrow">PENDING</span><b>${pendingAccess().length}</b><small>awaiting decision</small></div><div class="directory-mark">Access is tracked by the backend and applies per patient.</div></div>${form}${card('Connected patient directory',active.length?active.map(person=>`<div class="patient-record-row"><div class="avatar">${esc(person.name.split(/\s+/).map(x=>x[0]).join('').slice(0,2))}</div><div class="patient-record-main"><b>${esc(person.name)}</b><small>${esc(person.id)} Â· ${esc(person.email)}</small></div><div class="patient-record-meta">${pill('Connected','green')}</div><div class="patient-record-meta"><span class="eyebrow">LATEST MRI</span><b>${esc(person.lastMri||'Not recorded')}</b></div><div class="patient-row-action"><button class="button" data-open-patient="${person.id}">Open profile â†’</button></div></div>`).join(''):`<div class="empty-access"><div class="empty-icon">ï¼‹</div><b>No connected patients</b><p>Review an access request or create a request for an existing patient account.</p></div>`)}`;}
function backendAccessRequests(){
  const requests=state.accessRequests;
  const introduction=header('Access requests',state.role==='doctor'?'Approve or decline each patientâ€™s request before clinical access begins.':'Your personal care tabs are available while these requests are pending.');
  if(state.role==='patient'){
    const rows=requests.map(request=>`<div class="patient-row"><div class="grow"><b>${esc(request.name)}</b><small>${esc(request.status)} Â· ${esc(request.createdAt||'')}</small></div>${pill(request.status,request.status==='Approved'?'green':request.status==='Pending'?'amber':'red')}</div>`).join('');
    return `${introduction}${card('Clinician connection',rows||`<form id="access-form" class="access-form"><label>Clinician access code<input name="code" required maxlength="24" placeholder="Code shared by your clinician"></label><button class="button primary">Request access</button><p id="access-error" class="error hidden"></p></form>`)}`;
  }
  const rows=requests.map(request=>`<div class="patient-row"><div class="avatar">${esc(request.name.split(/\s+/).map(x=>x[0]).join('').slice(0,2))}</div><div class="grow"><b>${esc(request.name)}</b><small>${esc(request.patientId)} Â· Received ${esc(request.createdAt||'')}</small></div>${pill(request.status,request.status==='Approved'?'green':request.status==='Pending'?'amber':'red')}${request.status==='Pending'?`<button class="button primary" data-approve="${state.accessRequests.indexOf(request)}">Approve</button><button class="button" data-deny="${state.accessRequests.indexOf(request)}">Decline</button>`:''}</div>`).join('');
  return `${introduction}${card('Your clinician access code',`<div class="code-panel"><div><span class="eyebrow">SHARE THIS CODE WITH PATIENTS</span><b>${esc(state.doctorAccessCode||'Not available')}</b><small>Patients can submit a request using this code.</small></div></div>`)}${card('Requests',rows||'<div class="empty">No access requests yet.</div>')}`;
}
function backendProfile(){const person=selectedPatient(),profile=state.latestProfile;if(!person||!profile||!patientHasApprovedAccess(person.id))return `${header('Patient profile','Clinical information is available after access approval.')}${card('Access required','<div class="empty">Select a connected patient to open their information.</div>')}`;return DoctorPatientProfile({patient:{id:person.id,email:person.email,display_name:person.name},profile});}
function backendAssessment(){if(state.role==='patient'){const available=Boolean(state.latestProfile?.latest_assessment);return `${header('Assessment','A plain-language view of information saved to your record.')}${card('Imaging review',available?'<p>An MRI model assessment is saved and can be reviewed by your connected clinician.</p><p class="muted">Your care team remains responsible for interpreting imaging and discussing what it means for you.</p>':'<div class="empty">No MRI assessment is recorded.</div>')}`;}const result=state.latestStudy?.assessment||state.latestProfile?.latest_assessment||null;return DoctorAssessmentPage({result,studies:state.timelineFromApi?.studies||[],note:state.notes||''});}
function backendTimeline(){const timeline=state.timelineFromApi||{studies:[],ordering_complete:false};if(state.role==='patient')return PatientTimeline({studies:timeline.studies||[]});return `${header('Longitudinal MRI','Persisted dates, model output, and sourced measurements.')}${card('MRI history',LongitudinalTimeline(timeline))}`;}
function backendSurveillance(){const patient=state.role==='doctor'?selectedPatient():state.patient;if(state.role==='doctor')return DoctorSurveillance({patientId:Number(patient?.id||0),plans:(state.followups||[]).map(item=>({id:item.id,patient_user_id:Number(patient?.id||0),created_by_user_id:Number(state.user?.id||0),target_follow_up_date:item.date,interval:null,interval_unit:null,reason:item.reason,status:item.status,notes:null,last_reviewed_at:null,next_review_date:null,created_at:''}))});return `${header('Surveillance','Plans are created by clinicians and saved to your record.')}${card('Saved plans',state.followups.length?state.followups.map(item=>`<div class="patient-row"><div class="grow"><b>${esc(item.reason)}</b><small>${esc(item.date)} ? ${esc(item.status)}</small></div>${pill(item.status,'blue')}</div>`).join(''):'<div class="empty">No surveillance plan has been recorded.</div>')}`;}
function backendSymptoms(){return state.role==='patient'?PatientSymptoms({symptoms:state.symptoms||[]}):`${header('Symptoms','Patient-reported records for the selected patient.')}${card('Symptom history',(state.symptoms||[]).map(item=>`<div class="patient-row"><div class="grow"><b>${esc(item.symptom_type||item.name)}</b><small>${esc(item.onset_date||item.date||'Date not recorded')} ? ${esc(item.review_status||item.reviewStatus||'Pending review')}</small></div></div>`).join('')||'<div class="empty">No symptoms are stored.</div>')}`;}
function backendMedications(){const records=state.medicationRecords||[];if(state.role==='patient')return PatientMedications({records});return `${header('Medications','Medication candidates and verification state from saved OCR records.')}${card('Medication records',records.length?records.map(item=>MedicationCard(item,'doctor')).join(''):'<div class="empty">No medication records are stored.</div>')}${records.filter(item=>item.verification_status==='UNVERIFIED').map(item=>MedicationVerification(item)).join('')}<p class="muted">Extracted medication details remain unverified until a clinician checks the source.</p>`;}
function nutritionAlerts(summary){return (summary?.alerts||[]).map(alert=>`<div class="nutrition-alert nutrition-alert-${esc(String(alert.level||'review').toLowerCase())}"><b>${esc(alert.title)}</b><p>${esc(alert.summary)}</p></div>`).join('')||'<div class="empty">No nutrition review flags from the available records.</div>';}
function nutritionChart(summary){const days=(summary?.daily_estimates||[]).slice(-14),max=Math.max(1,...days.map(day=>day.calories_kcal||0));if(!days.length)return '<div class="empty">No image-based nutrition estimates are available.</div>';return `<div class="nutrition-chart">${days.map(day=>`<div class="nutrition-chart-column" title="${esc(day.date)}: ${Math.round(day.calories_kcal)} kcal"><span>${Math.round(day.calories_kcal)} kcal</span><i style="height:${Math.max(3,Math.round(day.calories_kcal/max*100))}%"></i><small>${esc(day.date.slice(5))}</small></div>`).join('')}</div><p class="muted">Estimated totals from analyzed images; unlogged meals and unconfirmed values may be missing. This chart is not a daily requirement target.</p>`;}
function nutritionSummaryPanel(summary){const average=summary?.average_per_logged_day,target=summary?.recorded_target||{},weight=summary?.weight||{};return `<div class="nutrition-metrics"><div><small>Average per logged day</small><b>${average?`~${Math.round(average.calories_kcal)} kcal`:'Unknown'}</b><small>${average?`Protein ~${Math.round(average.protein_g)} g`:''}</small></div><div><small>Clinician-entered energy target</small><b>${target.daily_kcal?`${Math.round(target.daily_kcal)} kcal/day`:'None recorded'}</b><small>${target.daily_protein_g?`Protein target ${Math.round(target.daily_protein_g)} g/day`:''}</small></div><div><small>Latest patient-reported weight</small><b>${weight.latest_kg?`${weight.latest_kg} kg`:'Not recorded'}</b><small>${weight.bmi?`BMI ${weight.bmi} Â· context only`:''}</small></div><div><small>Recorded meal entries</small><b>${summary?.meals?.length||0}</b><small>${(summary?.meals||[]).filter(item=>item.patient_confirmed).length} patient confirmed</small></div></div><p class="muted">${esc(summary?.average_basis||'No logged-day average available.')}</p>${summary?.target_notice?`<p class="nutrition-target-notice">${esc(summary.target_notice)}</p>`:''}`;}
function nutritionObservationForm(){return `<section class="card"><h2>Record todayâ€™s nutrition context</h2><form id="nutrition-observation-form"><div class="nutrition-edit-grid"><label>Weight (kg), if available<input name="weight_kg" type="number" min="1" max="500" step="0.1"></label><label>Height (cm), if available<input name="height_cm" type="number" min="1" max="250" step="0.1"></label><label>Appetite<select name="appetite"><option value="UNKNOWN">Not recorded</option><option value="GOOD">Good</option><option value="FAIR">Fair</option><option value="POOR">Poor</option></select></label></div><fieldset class="food-tags"><legend>Patient-reported symptoms today</legend>${[['DIARRHEA','Diarrhea'],['NAUSEA','Nausea'],['VOMITING','Vomiting'],['POOR_APPETITE','Poor appetite'],['EARLY_SATIETY','Early fullness'],['CONSTIPATION','Constipation'],['ABDOMINAL_PAIN','Abdominal pain'],['DIFFICULTY_SWALLOWING','Difficulty swallowing'],['TASTE_CHANGE','Taste change']].map(([value,label])=>`<label class="check"><input type="checkbox" name="reported_symptoms" value="${value}"> ${label}</label>`).join('')}</fieldset><label class="check"><input type="checkbox" name="intake_interfered"> Symptoms interfered with my intake</label><label class="check"><input type="checkbox" name="intake_day_complete"> I finished logging everything I ate today</label><p class="muted">Only mark the day complete when your meal log for that day is finished. Your entries are patient-reported.</p><button class="button primary">Save nutrition context</button></form></section>`;}
function nutritionTargetForm(summary){const target=summary?.recorded_target||{},context=summary?.documented_context||{};return `<section class="card"><h2>Clinician-recorded nutrition context</h2><p class="muted">Targets and condition context are entered by the care team. No target is calculated automatically.</p><form id="nutrition-profile-form"><div class="nutrition-edit-grid"><label>Daily energy target (kcal)<input name="target_daily_kcal" type="number" min="1" max="10000" step="1" value="${target.daily_kcal||''}"></label><label>Daily protein target (g)<input name="target_daily_protein_g" type="number" min="1" max="1000" step="1" value="${target.daily_protein_g||''}"></label></div><label class="check"><input name="documented_pei_pert" type="checkbox" ${context.pei_pert?'checked':''}> PEI/PERT context documented</label><label class="check"><input name="documented_diabetes" type="checkbox" ${context.diabetes?'checked':''}> Diabetes/glucose-management context documented</label><button class="button primary">Save clinical context</button></form></section>`;}
function backendMeals(){const entries=state.meals||[];return state.role==='patient'?PatientMeals({meals:entries,summary:state.nutritionSummary}):`${header('Meals','Meal estimates, patient confirmations, context flags, and provenance for the selected patient.')}${!state.selectedPatientId?'<div class="empty">Select an approved patient to review meal entries.</div>':card('Patient meal history',entries.map(item=>MealEntry(item,false)).join('')||'<div class="empty">No meal entries are stored.</div>')}`;}
function backendNutrition(){const summary=state.nutritionSummary,person=state.role==='doctor'?selectedPatient():state.patient;if(state.role==='doctor'&&!patientHasApprovedAccess(person?.id))return `${header('Nutrition','Nutrition records require an active patient access grant.')}${card('Access required','<div class="empty">Select an approved patient before reviewing nutrition information.</div>')}`;return `${header('Nutrition monitoring',state.role==='doctor'?`Patient-reported intake and context for ${esc(person?.name||'the selected patient')}.`:'Review your recorded meal estimates, weight, appetite, and symptom context.')}${nutritionAlerts(summary)}${card('Estimated intake trend',nutritionChart(summary))}${card('Nutrition summary',nutritionSummaryPanel(summary))}${state.role==='patient'?nutritionObservationForm():nutritionTargetForm(summary)}${card('Recent meals',NutritionTimeline(state.meals||[]))}<p class="fine-print">${esc(summary?.alert_disclaimer||'Estimates support monitoring and do not provide diagnoses, treatment instructions, or medication changes.')}</p>`;}
function backendMessages(){const patient=state.role==='patient'?state.patient:selectedPatient();return `${header('Messages','Messages are visible to the patient and clinicians with an active connection.')}${state.role==='patient'&&!patientHasApprovedAccess(patient.id)?card('Care team connection required','<div class="empty">You can use your other care tabs now. A clinician must approve your connection before secure care-team messaging is enabled.</div>'):''}${card('Care-team conversation',`${state.messages.map(message=>`<div class="message ${message.from==='patient'?'mine':''}"><p>${esc(message.text)}</p><small>${esc(message.time)}</small></div>`).join('')||'<div class="empty">No messages are stored.</div>'}${state.role==='doctor'||patientHasApprovedAccess(patient.id)?`<form id="message-form" class="form-row"><label>Message<input name="text" required maxlength="10000" placeholder="Write a care-team message"></label><button class="button primary">Send</button><p id="api-error" class="error hidden"></p></form>`:''}<p class="muted">Do not use messages for emergencies.</p>`)}`;}
function backendCareLoop(){return PatientCareLoop({events:state.careEvents||[]});}
function backendVisitPreparation(){const profile=state.latestProfile||{};return PatientVisitPreparation({questions:state.questions||[],latestMRI:profile.latest_mri?.study_date,symptomCount:state.symptoms.length,medicationCount:state.medicationRecords?.length||0,mealCount:state.meals.length,followupCount:state.followups.length});}
function backendReports(){const profile=state.latestProfile||{},records=state.reportRecords||[];if(state.role==='doctor'){const person=selectedPatient(),preview=DoctorReports({patient:{id:Number(person?.id||0),email:person?.email||'',display_name:person?.name||''},profile,note:state.notes||''}),patientReports=state.selectedPatientReports||[];const docs=patientReports.map(record=>{const fields=record.verified_fields||Object.fromEntries(Object.entries(record.fields||{}).map(([name,field])=>[name,field?.value??'']));const rows=Object.entries(record.fields||{}).map(([name,field])=>`<label>${esc(name.replace(/_/g,' '))}<input name="${esc(name)}" value="${esc(fields[name]??'')}" ${record.document.verification_status==='VERIFIED'?'readonly':''}></label>`).join('');return card(`Patient report Â· ${esc(record.document.original_filename)}`,`<p>${esc(record.document.extraction_status)} Â· ${esc(record.document.verification_status)}</p><form id="report-verify-form" class="report-verify-form" data-report-id="${esc(record.id)}"><div class="form-grid">${rows}</div><label>Clinician note<textarea name="doctor_note" maxlength="2000" ${record.document.verification_status==='VERIFIED'?'readonly':''}>${esc(record.doctor_note||'')}</textarea></label>${record.document.verification_status!=='VERIFIED'?'<button class="button primary">Verify reviewed fields</button>':''}<p class="fine-print">OCR values are candidate information. Review against the source before verification.</p></form>`);}).join('')||card('Patient reports','<div class="empty">No reports have been uploaded by this patient.</div>');return `${preview}${docs}`;}const upload=card('Upload medical report',`<form id="report-upload-form"><label>Report PDF or image<input type="file" name="upload" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" required></label><button class="button primary">Upload report</button><p id="api-error" class="error hidden"></p></form>`);const docs=records.length?records.map(record=>card(`Medical report Â· ${esc(record.document.original_filename)}`,`<p>${esc(record.document.extraction_status)} Â· ${esc(record.document.verification_status)}</p>${Object.entries(record.verified_fields||record.fields||{}).map(([name,field])=>`<p><b>${esc(name.replace(/_/g,' '))}:</b> ${field?.value==null?'Unknown':esc(field.value)}</p>`).join('')}`)).join(''):card('Uploaded reports','<div class="empty">No report documents are stored.</div>');return `${header('Reports','Uploaded report OCR remains reviewable candidate information.')}${upload}${docs}`;}
function backendPageContent(){if(state.role==='doctor'&&['Patient Profile','MRI Analysis','Assessment','Timeline','Meals','Nutrition','Surveillance','Reports','Messages'].includes(page)&&!patientHasApprovedAccess(state.selectedPatientId))return `${header(page,'Select a connected patient before opening clinical records.')}${card('Patient access required',`<div class="empty">This page is available after you select a patient with an active access grant.</div>${link('Open patients','Patients')}`)}`;switch(page){case 'Dashboard':return state.role==='doctor'?backendDoctorHome():backendPatientDashboard();case 'Patients':return backendPatients();case 'Access Requests':return backendAccessRequests();case 'Care Team Access':return backendAccessRequests();case 'Patient Profile':return backendProfile();case 'MRI Analysis':return mri();case 'Assessment':return backendAssessment();case 'Timeline':return backendTimeline();case 'Surveillance':return backendSurveillance();case 'Reports':return backendReports();case 'CareLoop':return backendCareLoop();case 'Symptoms':return backendSymptoms();case 'Medications':return backendMedications();case 'Meals':return backendMeals();case 'Nutrition':return backendNutrition();case 'Visit Preparation':return backendVisitPreparation();case 'Messages':return backendMessages();default:return state.role==='doctor'?backendDoctorHome():backendPatientDashboard();}}
function showFormError(id, error) { const target=document.getElementById(id);if(target){target.textContent=error?.message||String(error);target.classList.remove('hidden');}else{state.apiError=error?.message||String(error);render();} }
function installBackendHandlers() {
  document.addEventListener('submit', async event => {
    const form=event.target, supported=['role-login-form','auth-register-form','doctor-add-patient-form','access-form','symptom-form','followup-form','question-form','meal-form','food-analyze-form','meal-confirm-form','nutrition-observation-form','nutrition-profile-form','message-form','medication-upload-form','medication-verify-form','medication-conflict-form','report-upload-form','report-verify-form'];
    if(!supported.includes(form.id))return;
    event.preventDefault();event.stopImmediatePropagation();
    const data=Object.fromEntries(new FormData(form));
    try {
      if(form.id==='role-login-form'||form.id==='auth-register-form'){
        const register=form.id==='auth-register-form',expectedRole=authRole==='doctor'?'DOCTOR':'PATIENT';
        const user=await authenticate({email:data.email,password:data.password,display_name:data.name,role:expectedRole,doctor_access_code:data.code},register);
        if(user.role!==expectedRole){clearSession();throw new Error(`This account belongs to the ${user.role==='DOCTOR'?'clinician':'patient'} portal.`);}
        await finishAuthentication(user);return;
      }
      if(form.id==='doctor-add-patient-form'){
        await apiRequest('/patients/access-requests/invite',{method:'POST',body:{email:String(data.email).trim().toLowerCase()}});
        state.addPatientOpen=false;await refreshBackendData();return;
      }
      if(form.id==='access-form'){
        await apiRequest('/patients/access-requests',{method:'POST',body:{doctor_access_code:String(data.code||'').trim().toUpperCase()}});
        await refreshBackendData();return;
      }
      if(form.id==='food-analyze-form'){
        const body=new FormData(form);await apiRequest('/food/meals/analyze',{method:'POST',body});await refreshBackendData();return;
      }
      if(form.id==='meal-confirm-form'){
        const values=new FormData(form),nutrition={};
        for(const key of ['calories_kcal','protein_g','carbohydrates_g','fat_g'])if(String(values.get(key)||'').trim()!=='')nutrition[key]=Number(values.get(key));
        const portion=String(values.get('estimated_portion_grams')||'').trim();
        const body={confirmed:true,description:String(values.get('description')||''),food_items:String(values.get('food_items')||'').split(',').map(x=>x.trim()).filter(Boolean),food_context_tags:values.getAll('food_context_tags')};
        if(Object.keys(nutrition).length)body.nutrition=nutrition;if(portion)body.estimated_portion_grams=Number(portion);
        const confirmed=form.dataset.confirmed==='true',path=`/food/meals/${encodeURIComponent(form.dataset.mealId)}`;
        if(confirmed)await apiRequest(path,{method:'PATCH',body});else await apiRequest(`${path}/confirm`,{method:'POST',body});await refreshBackendData();return;
      }
      if(form.id==='nutrition-observation-form'){
        const values=new FormData(form),weight=String(values.get('weight_kg')||'').trim(),height=String(values.get('height_cm')||'').trim();
        const body={appetite:values.get('appetite'),reported_symptoms:values.getAll('reported_symptoms'),intake_interfered:values.has('intake_interfered'),intake_day_complete:values.has('intake_day_complete')};
        if(weight)body.weight_kg=Number(weight);if(height)body.height_cm=Number(height);
        await apiRequest(`/patients/${state.user.id}/nutrition/observations`,{method:'POST',body});await refreshBackendData();return;
      }
      if(form.id==='nutrition-profile-form'){
        const values=new FormData(form),kcal=String(values.get('target_daily_kcal')||'').trim(),protein=String(values.get('target_daily_protein_g')||'').trim();
        const body={documented_pei_pert:values.has('documented_pei_pert'),documented_diabetes:values.has('documented_diabetes'),target_daily_kcal:kcal?Number(kcal):null,target_daily_protein_g:protein?Number(protein):null};
        await apiRequest(`/patients/${state.selectedPatientId}/nutrition/profile`,{method:'POST',body});await loadSelectedDoctorPatient();render();return;
      }
      const patientId=state.user.id;
      if(form.id==='symptom-form'){
        const severity={Mild:2,Moderate:5,Severe:8}[data.severity]||null;
        await apiRequest(`/patients/${patientId}/symptoms`,{method:'POST',body:{symptom_type:data.name,severity,onset_date:data.date||null,notes:data.note||null,status:'ACTIVE'}});
        await refreshBackendData();return;
      }
      if(form.id==='followup-form'){
        if(state.role!=='doctor')throw new Error('Only the care team can create a surveillance plan.');
        await apiRequest(`/patients/${state.selectedPatientId}/surveillance`,{method:'POST',body:{target_follow_up_date:data.date,reason:data.reason}});
        await loadSelectedDoctorPatient();render();return;
      }
      if(form.id==='question-form'){
        await apiRequest(`/patients/${patientId}/notes`,{method:'POST',body:{body:data.question,visibility:'PATIENT_VISIBLE',source_context:'VISIT_PREPARATION'}});
        await refreshBackendData();return;
      }
      if(form.id==='meal-form'){
        await apiRequest(`/patients/${patientId}/meals`,{method:'POST',body:{description:data.name,patient_confirmed:data.confirm==='on'}});
        await refreshBackendData();return;
      }
      if(form.id==='message-form'){
        const conversationPatientId=state.role==='doctor'?state.selectedPatientId:patientId;
        if(!conversationPatientId)throw new Error('Select an approved patient before sending a care-team message.');
        await apiRequest(`/patients/${conversationPatientId}/messages`,{method:'POST',body:{body:data.text}});
        await refreshBackendData();return;
      }
      if(form.id==='medication-upload-form'){
        const body=new FormData(form);
        await apiRequest('/medications/documents',{method:'POST',body});
        await refreshBackendData();return;
      }
      if(form.id==='medication-verify-form'){
        const allowed=new Set(['name','generic_name','brand_name','strength','normalized_strength','dose','dosage_form','frequency','normalized_frequency','route','normalized_route','start_date','end_date','duration','prescriber','indication']);
        const fields=Object.fromEntries(Object.entries(data).filter(([key])=>allowed.has(key)));
        await apiRequest(`/medications/${form.dataset.medicationId}/verify`,{method:'POST',body:{fields,medication_status:data.medication_status||null,doctor_note:data.doctor_note||null}});
        await loadSelectedDoctorPatient();render();return;
      }
      if(form.id==='medication-conflict-form'){
        await apiRequest(`/patients/${state.user.id}/medications/${form.dataset.medicationId}/review-conflict`,{method:'POST',body:{review_note:data.review_note,resolution_record_id:data.resolution_record_id}});
        await refreshBackendData();return;
      }
      if(form.id==='report-upload-form'){
        const body=new FormData(form);
        await apiRequest('/reports/documents',{method:'POST',body});
        await refreshBackendData();page='Reports';render();return;
      }
      if(form.id==='report-verify-form'){
        const data=Object.fromEntries(new FormData(form));
        const fields=Object.fromEntries(Object.entries(data).filter(([key])=>key!=='doctor_note').map(([key,value])=>[key,value===''?null:value]));
        await apiRequest(`/reports/${encodeURIComponent(form.dataset.reportId)}/verify`,{method:'POST',body:{fields,doctor_note:data.doctor_note||null}});
        await loadSelectedDoctorPatient();render();return;
      }
    } catch(error) { showFormError(form.id==='role-login-form'||form.id==='auth-register-form'?'auth-error':form.id==='access-form'?'access-error':form.id==='food-analyze-form'?'food-analysis-error':form.id==='meal-confirm-form'?`meal-error-${form.dataset.mealId}`:'api-error',error); }
  },true);

  document.addEventListener('click', async event => {
    const target=event.target.closest('[data-action="logout"],[data-action="review"],[data-action="print-report"],[data-action="uncertain-meal"],[data-open-patient],[data-approve],[data-deny],[data-complete]');
    if(!target)return;
    try {
      if(target.dataset.action==='logout'){
        clearSession();state.user=null;state.backendConnected=false;state.role=null;state.sessionRestoring=false;state.apiError='';state.patient={...primaryPatient};
        state.patientDirectory=[];state.accessRequests=[];state.symptoms=[];state.meals=[];state.messages=[];page='Dashboard';render();return;
      }
      if(target.dataset.action==='uncertain-meal'){
        const form=target.closest('form'),values=new FormData(form),body={confirmed:false,description:String(values.get('description')||''),food_items:String(values.get('food_items')||'').split(',').map(x=>x.trim()).filter(Boolean),food_context_tags:values.getAll('food_context_tags')};
        await apiRequest(`/food/meals/${encodeURIComponent(target.dataset.mealId)}/confirm`,{method:'POST',body});await refreshBackendData();return;
      }
      if(target.dataset.action==='print-report'){window.print();return;}
      if(target.dataset.openPatient){
        state.selectedPatientId=Number(target.dataset.openPatient);
        await loadSelectedDoctorPatient();render();return;
      }
      if(target.dataset.action==='review'){
        const reviewNote=document.getElementById('clinical-notes')?.value||state.notes||'';
        const assessment=document.getElementById('clinician-assessment')?.value||'';
        await apiRequest(`/patients/${state.selectedPatientId}/notes`,{method:'POST',body:{body:[assessment,reviewNote].filter(Boolean).join('\n\n')||'Clinician reviewed the stored MRI assessment.',visibility:'CLINICIAN_ONLY',source_context:'MRI_ASSESSMENT_REVIEW'}});
        await apiRequest(`/patients/${state.selectedPatientId}/reviews`,{method:'POST',body:{item_type:'MRI_ASSESSMENT_REVIEW',priority:'NORMAL',description:assessment||'Clinician recorded an assessment review.'}});
        await loadSelectedDoctorPatient();state.apiError='';render();return;
      }
      if(target.dataset.approve!==undefined||target.dataset.deny!==undefined){
        const request=state.accessRequests[Number(target.dataset.approve??target.dataset.deny)];
        if(!request)return;
        const action=target.dataset.approve!==undefined?'approve-access':'decline-access';
        await apiRequest(`/patients/${request.patientId}/doctors/${state.user.id}/${action}`,{method:'POST'});
        await refreshBackendData();return;
      }
      if(target.dataset.complete!==undefined){
        const plan=state.followups[Number(target.dataset.complete)];
        if(!plan?.id)return;
        await apiRequest(`/patients/${state.selectedPatientId}/surveillance/${plan.id}/complete`,{method:'POST'});
        await loadSelectedDoctorPatient();render();
      }
    } catch(error) { state.apiError=error.message;render(); }
  });
  document.addEventListener('click', async event=>{
    const nav=event.target.closest('[data-go]');
    if(!nav||!state.backendConnected)return;
    try{if(['Dashboard','Patients','Access Requests','Care Team Access'].includes(nav.dataset.go))await refreshBackendData();}
    catch(error){state.apiError=error.message;render();}
  });
}
function render() { const root=document.getElementById('app'); if(state.sessionRestoring){root.innerHTML='<main class="login"><section class="login-card"><b>Connecting to CystGuardâ€¦</b><p class="muted">Restoring your secure session.</p></section></main>';return;}root.innerHTML=state.role?shell(state.backendConnected?backendPageContent():pageContent()):authPage();if(!state.role&&state.apiError){const error=root.querySelector('#auth-error');if(error){error.textContent=state.apiError;error.classList.remove('hidden');}} }
async function restoreSession(){if(!getAccessToken()){state.sessionRestoring=false;render();return;}try{const user=await apiRequest('/auth/me');await finishAuthentication(user);}catch(error){clearSession();state.user=null;state.backendConnected=false;state.role=null;state.apiError='';state.sessionRestoring=false;render();}}
async function runAnalysis(){const file=document.getElementById('mri-file')?.files?.[0];const validation=document.getElementById('validation');if(!file){if(validation)validation.innerHTML='<p class="error">Select a .nii MRI file to continue.</p>';return;}const fileError=validateMRIFile(file);if(fileError){if(validation)validation.innerHTML=`<p class="error">${esc(fileError)}</p>`;return;}if(!state.backendConnected){state.apiError='Sign in to upload and analyze an MRI.';render();return;}const patient=selectedPatient();state.uploadName=file.name;state.uploadStatus='processing';state.analysis={status:'running',progress:15,stage:1};render();try{const body=new FormData();body.append('upload',file);if(state.role==='doctor'&&state.selectedPatientId)body.append('patient_id',String(state.selectedPatientId));const response=await apiRequest('/mri/studies',{method:'POST',body});const a=response.assessment,s=response.mri_study;const result={score:a.raw_score,threshold:a.threshold,riskClass:a.risk_class,profile:a.risk_class||'Assessment unavailable',date:s.study_date||s.uploaded_at?.slice(0,10),evidence:[],studyId:s.id,assessmentId:a.id};state.analysis={status:a.prediction_status==='SUCCESS'?'complete':'failed',progress:100,stage:4,result,patientId:patient.id};state.uploadStatus='complete';state.latestStudy=response;patient.lastMri=result.date||'';patient.latestAnalysis=result;await refreshBackendData();if(state.role==='doctor')await loadSelectedDoctorPatient();render();}catch(error){state.analysis={status:'failed',progress:0,stage:0};state.uploadStatus='';state.apiError=error.message;render();}}
document.addEventListener('click',e=>{const t=e.target.closest('[data-auth-role],[data-auth-mode]');if(!t)return;if(t.dataset.authRole){authRole=t.dataset.authRole;authMode='login';render();}if(t.dataset.authMode){authMode=t.dataset.authMode;render();}});
document.addEventListener('click',e=>{const t=e.target.closest('[data-go],[data-action],[data-login],[data-complete],[data-remove-question],[data-approve],[data-deny],[data-open-patient]');if(!t)return;if(t.dataset.go){page=t.dataset.go;render();}if(t.dataset.openPatient){if(state.analysis?.patientId!==t.dataset.openPatient){state.analysis={status:'idle',progress:0,stage:0};state.uploadName='';state.uploadStatus='';}state.selectedPatientId=t.dataset.openPatient;page='Patient Profile';save();render();}if(t.dataset.login){state.role=t.dataset.login;page='Dashboard';save();render();}if(t.dataset.action==='logout'){state.role=null;save();render();}if(t.dataset.action==='toggle-add-patient'){state.addPatientOpen=!state.addPatientOpen;render();}if(t.dataset.action==='mri'){page='MRI Analysis';render();}if(t.dataset.action==='clear-mri'){const input=document.getElementById('mri-file');if(input)input.value='';state.uploadName='';state.uploadStatus='';render();}if(t.dataset.action==='start-analysis')runAnalysis();if(t.dataset.action==='reset-analysis'){state.uploadName='';state.uploadStatus='';state.analysis={status:'idle',progress:0,stage:0};save();render();}if(t.dataset.action==='review'){state.notes=document.getElementById('clinical-notes').value;state.assessment=document.getElementById('clinician-assessment').value||'Reviewed; see clinical notes';state.reviewed=true;save();render();}if(t.dataset.complete!==undefined){state.followups[Number(t.dataset.complete)].status='Completed';save();render();}if(t.dataset.removeQuestion!==undefined){state.questions.splice(Number(t.dataset.removeQuestion),1);save();render();}if(t.dataset.approve!==undefined){const r=state.accessRequests[Number(t.dataset.approve)];if(r){r.status='Approved';r.reviewedAt=new Date().toLocaleString();}save();render();}if(t.dataset.deny!==undefined){const r=state.accessRequests[Number(t.dataset.deny)];if(r){r.status='Declined';r.reviewedAt=new Date().toLocaleString();}save();render();}});
document.addEventListener('change',e=>{if(e.target?.id==='mri-file'){const file=e.target.files?.[0],out=document.getElementById('validation'),name=document.getElementById('file-status');if(!file)return;const issue=validateMRIFile(file),size=file.size<1024*1024?`${(file.size/1024).toFixed(1)} KB`:`${(file.size/1024/1024).toFixed(1)} MB`;state.uploadName=issue?'':file.name;if(name)name.textContent=issue?'No valid file selected':`${file.name} ? ${size}`;if(out)out.innerHTML=issue?`<p class="error">${esc(issue)}</p>`:`<p class="success">.nii file selected ? ${size}</p><button type="button" class="text-button" data-action="clear-mri">Remove selected file</button>`;}else if(e.target?.matches?.('select[aria-label]')){state.kyoto[e.target.getAttribute('aria-label')]=e.target.value;save();}else if(e.target?.id==='meal-photo')refreshMealEstimate();});
document.addEventListener('input',e=>{if(e.target.id==='meal-description')refreshMealEstimate();});
document.addEventListener('submit',e=>{if(e.target.id!=='role-login-form'||authRole!=='patient')return;const email=new FormData(e.target).get('email')?.toString().trim().toLowerCase();const seed=patientSeeds.find(person=>person.email===email);if(seed){state.patient={...seed};state.symptoms=[...seed.symptoms];state.meals=[...seed.meals];state.kyoto={};state.uploadName='';state.uploadStatus='';state.analysis={status:'idle',progress:0,stage:0};save();}});
document.addEventListener('submit',e=>{e.preventDefault();const form=e.target;const d=Object.fromEntries(new FormData(form));if(form.id==='doctor-add-patient-form'){const name=String(d.name||'').trim(),email=String(d.email||'').trim().toLowerCase();const error=document.getElementById('patient-form-error');if(state.patientDirectory.some(person=>person.email?.toLowerCase()===email)){error.textContent='A patient with this email is already in the directory.';error.classList.remove('hidden');return;}let id;do{id='CG-'+Math.floor(1000+Math.random()*9000);}while(state.patientDirectory.some(person=>person.id===id));const person={id,name,email,age:d.age?Number(d.age):null,diagnosis:String(d.diagnosis||'').trim()||'Care information pending',doctorId:clinicianSeed.id,lastMri:'',nextVisit:'To be scheduled',symptoms:[],meals:[]};state.patientDirectory.unshift(person);state.addPatientOpen=false;save();render();return;}if(form.id==='patient-register-form'){const entered=String(d.code||'').trim().toUpperCase();const error=document.getElementById('auth-error');if(entered!==state.doctorAccessCode.toUpperCase()){error.textContent='That clinician code could not be verified. Check it with your care team and try again.';error.classList.remove('hidden');return;}const email=String(d.email||'').trim().toLowerCase();const invited=state.patientDirectory.find(person=>person.email?.toLowerCase()===email);state.patient=invited?{...invited}:{...state.patient,name:d.name.trim(),email,id:'CG-'+Math.floor(1000+Math.random()*9000)};if(invited)state.patient.name=d.name.trim()||invited.name;state.patientDirectory=state.patientDirectory.filter(person=>person.id!==state.patient.id);state.patientDirectory.push({...state.patient});state.accessRequests=state.accessRequests.filter(r=>r.patientId!==state.patient.id);state.accessRequests.push({name:state.patient.name,patientId:state.patient.id,doctorCode:entered,status:'Pending',reference:'CG-'+Math.random().toString(36).slice(2,8).toUpperCase(),createdAt:new Date().toLocaleString()});state.role='patient';page='Care Team Access';save();render();return;}if(form.id==='role-login-form'){state.role=authRole;page='Dashboard';save();render();return;}if(form.id==='access-form'){const entered=String(d.code||'').trim().toUpperCase();const error=document.getElementById('access-error');if(entered!==state.doctorAccessCode.toUpperCase()){error.textContent='We could not match that clinician code. Check the code and try again.';error.classList.remove('hidden');return;}const request={name:state.patient.name,patientId:state.patient.id,doctorCode:entered,status:'Pending',reference:'CG-'+Math.random().toString(36).slice(2,8).toUpperCase(),createdAt:new Date().toLocaleString()};state.accessRequests.push(request);save();render();return;}if(form.id==='symptom-form')state.symptoms.unshift({name:d.name,severity:d.severity,date:d.date,note:d.note});if(form.id==='followup-form')state.followups.unshift({date:d.date,reason:d.reason,status:'Upcoming'});if(form.id==='question-form')state.questions.push(d.question);if(form.id==='message-form')state.messages.push({from:state.role==='patient'?'patient':'doctor',text:d.text,time:new Date().toLocaleString()});if(form.id==='meal-form'){const estimate=estimateMeal(d.name,d.image?.name||'',state.meals.length);state.meals.unshift({name:d.name,date:'Today',...estimate,confirmed:d.confirm==='on'});}save();render();});
render();

function formEvidence(source, verification, field){return [{source_type:'CLINICAL_HISTORY',source_id:'clinician-entered',field,evidence_reference:source||null,verification_status:verification||'UNVERIFIED'}];}
function installClinicalAssessmentHandlers(){
  document.addEventListener('submit',async event=>{
    const form=event.target;
    if(form?.id!=='clinical-context-form')return;
    event.preventDefault();event.stopImmediatePropagation();
    const error=document.getElementById('clinical-context-error');
    try{
      const updated=await api.mri.clinicalContext(form.dataset.assessmentId,buildClinicalContextPayload(form));
      if(state.latestStudy)state.latestStudy={...state.latestStudy,assessment:updated};
      else state.latestStudy={assessment:updated,mri_study:{id:updated.mri_study_id,modality:'T1'}};
      render();
    }catch(err){if(error){error.textContent=err.message;error.classList.remove('hidden');}}
  },true);
  document.addEventListener('click',async event=>{
    const button=event.target.closest('[data-explanation-refresh]');
    const assessmentId=button?.dataset.assessmentId||state.latestStudy?.assessment?.id;
    if(!button||!assessmentId)return;
    event.preventDefault();
    try{
      const assessment=await api.mri.explanation(assessmentId);
      if(state.latestStudy?.assessment?.id===assessmentId)state.latestStudy={...state.latestStudy,assessment};
      if(state.latestProfile?.latest_assessment?.id===assessmentId)state.latestProfile={...state.latestProfile,latest_assessment:assessment};
      if(!state.latestStudy?.assessment)state.latestStudy={assessment,mri_study:{id:assessment.mri_study_id,modality:'T1'}};
      render();
    }catch(error){state.apiError=error.message;render();}
  },true);
}
installClinicalAssessmentHandlers();
installBackendHandlers();
void restoreSession();
