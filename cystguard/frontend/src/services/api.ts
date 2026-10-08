import type { AccessRequest, CareProfile, MealEntry, MedicalReport, MedicationRecord, MRIAnalysisResponse, MRIStudySummary, SurveillancePlan, Symptom } from '../types/patient.js';
import type { CurrentUser, LoginRequest, RegisterRequest, TokenResponse } from '../types/auth.js';
import type { MealEntry as NutritionMealEntry, NutritionSummary } from '../types/meal.js';

declare global { interface Window { CYSTGUARD_API_URL?: string } }
const API_BASE = (window.CYSTGUARD_API_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
const TOKEN_KEY = 'cystguard-access-token';

export class ApiError extends Error {
  constructor(readonly status: number, message: string, readonly payload?: unknown) { super(message); this.name = 'ApiError'; }
}
export function getAccessToken(): string | null { return localStorage.getItem(TOKEN_KEY); }
export function setAccessToken(token: string | null): void { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY); }
function responseError(payload: unknown, status: number): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((entry) => typeof entry === 'object' && entry && 'msg' in entry ? String(entry.msg) : String(entry)).join('. ');
  }
  return `Request failed (${status})`;
}
export async function apiRequest<T = unknown>(path: string, options: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown; headers?: HeadersInit; auth?: boolean } = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, auth = true } = options;
  const requestHeaders = new Headers(headers);
  const token = getAccessToken();
  // Protected requests must never reach the API until a session token exists.
  // Public routes such as health, register, and login opt out with auth:false.
  if (auth && !token) throw new ApiError(401, 'Sign in to continue.');
  if (auth && token) requestHeaders.set('Authorization', `Bearer ${token}`);
  let requestBody: BodyInit | undefined;
  if (body instanceof FormData || typeof body === 'string') requestBody = body;
  else if (body !== undefined) { requestHeaders.set('Content-Type', 'application/json'); requestBody = JSON.stringify(body); }
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { method, headers: requestHeaders, body: requestBody }); }
  catch { throw new ApiError(0, 'Cannot reach CystGuard services. Check that the API is running.'); }
  const contentType = response.headers.get('content-type') || '';
  const payload: unknown = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = response.status === 404 ? `Not Found: ${method} ${path}` : responseError(payload, response.status);
    throw new ApiError(response.status, message, payload);
  }
  return payload as T;
}
export async function authenticate(input: RegisterRequest | LoginRequest, register = false): Promise<CurrentUser> {
  if (register) await apiRequest<CurrentUser>('/auth/register', { method: 'POST', auth: false, body: input });
  const session = await apiRequest<TokenResponse>('/auth/login', { method: 'POST', auth: false, body: input });
  setAccessToken(session.access_token);
  try { return await apiRequest<CurrentUser>('/auth/me'); } catch (error) { setAccessToken(null); throw error; }
}
export function clearSession(): void { setAccessToken(null); }
export const api = {
  health: () => apiRequest<{ status: string; version: string }>('/health', { auth: false }),
  currentUser: () => apiRequest<CurrentUser>('/auth/me'),
  patients: {
    profile: (id: number) => apiRequest<CareProfile>(`/patients/${id}/care-profile`),
    symptoms: (id: number) => apiRequest<Symptom[]>(`/patients/${id}/symptoms`),
    addSymptom: (id: number, body: Record<string, unknown>) => apiRequest<Symptom>(`/patients/${id}/symptoms`, { method: 'POST', body }),
    doctorAccessRequests: () => apiRequest<AccessRequest[]>('/patients/access-requests'),
    accessRequests: (id: number) => apiRequest<AccessRequest[]>(`/patients/${id}/access-requests`),
    requestAccess: (doctor_access_code: string) => apiRequest<AccessRequest>('/patients/access-requests', { method: 'POST', body: { doctor_access_code } }),
    directory: () => apiRequest<AccessRequest[]>('/patients/directory'),
    meals: (id: number) => apiRequest<MealEntry[]>(`/patients/${id}/meals`),
    addMeal: (id: number, body: { description: string; patient_confirmed: boolean }) => apiRequest<MealEntry>(`/patients/${id}/meals`, { method: 'POST', body }),
    messages: (id: number) => apiRequest<Array<{ id: string; sender_user_id: number; body: string; created_at: string }>>(`/patients/${id}/messages`),
    sendMessage: (id: number, body: string) => apiRequest(`/patients/${id}/messages`, { method: 'POST', body: { body } }),
    notes: (id: number) => apiRequest<Array<{ id: string; body: string; visibility: string; created_at: string }>>(`/patients/${id}/notes`),
    careloop: (id: number) => apiRequest<Array<Record<string, unknown>>>(`/patients/${id}/careloop`),
    visitPreparation: (id: number) => apiRequest<Record<string, unknown>>(`/patients/${id}/visit-preparation`),
    reviews: (id: number) => apiRequest<Array<Record<string, unknown>>>(`/patients/${id}/reviews`),
  },
  mri: {
    upload: (file: File, patientId?: number) => { const form = new FormData(); form.append('upload', file); if (patientId !== undefined) form.append('patient_id', String(patientId)); return apiRequest<MRIAnalysisResponse>('/mri/studies', { method: 'POST', body: form }); },
    study: (id: string) => apiRequest<MRIAnalysisResponse>(`/mri/studies/${encodeURIComponent(id)}`),
    assessment: (id: string) => apiRequest(`/mri/assessments/${encodeURIComponent(id)}`),
    clinicalContext: (id: string, body: Record<string, unknown>) => apiRequest(`/mri/assessments/${encodeURIComponent(id)}/clinical-context`, { method: 'POST', body }),
    explanation: (id: string) => apiRequest(`/mri/assessments/${encodeURIComponent(id)}/explanation`, { method: 'POST' }),
    timeline: (id: number) => apiRequest<{ studies: MRIStudySummary[]; ordering_complete: boolean }>(`/patients/${id}/mri/timeline`),
    compare: (patientId: number, previousId: string, currentId: string) => apiRequest(`/patients/${patientId}/mri/compare?previous_study_id=${encodeURIComponent(previousId)}&current_study_id=${encodeURIComponent(currentId)}`),
  },
  surveillance: {
    list: (id: number) => apiRequest<SurveillancePlan[]>(`/patients/${id}/surveillance`),
    create: (id: number, body: Record<string, unknown>) => apiRequest<SurveillancePlan>(`/patients/${id}/surveillance`, { method: 'POST', body }),
    complete: (patientId: number, planId: string) => apiRequest(`/patients/${patientId}/surveillance/${encodeURIComponent(planId)}/complete`, { method: 'POST' }),
  },
  reports: {
    list: () => apiRequest<MedicalReport[]>('/reports'),
    upload: (file: File) => { const form = new FormData(); form.append('upload', file); return apiRequest<MedicalReport>('/reports/documents', { method: 'POST', body: form }); },
    read: (id: string) => apiRequest<MedicalReport>(`/reports/${encodeURIComponent(id)}`),
  },
  medications: {
    list: (id: number) => apiRequest<MedicationRecord[]>(`/patients/${id}/medications`),
    upload: (file: File) => { const form = new FormData(); form.append('upload', file); return apiRequest('/medications/documents', { method: 'POST', body: form }); },
    ocr: (id: string) => apiRequest(`/medications/ocr/${encodeURIComponent(id)}`),
    verify: (id: string, body: Record<string, unknown>) => apiRequest(`/medications/${encodeURIComponent(id)}/verify`, { method: 'POST', body }),
    reviewConflict: (patientId: number, medicationId: string, body: { review_note: string; resolution_record_id: string }) => apiRequest(`/patients/${patientId}/medications/${encodeURIComponent(medicationId)}/review-conflict`, { method: 'POST', body }),
  },
  food: {
    analyzeMeal: (body: FormData) => apiRequest<NutritionMealEntry>('/food/meals/analyze', { method: 'POST', body }),
    confirmMeal: (id: string, body: Record<string, unknown>) => apiRequest<NutritionMealEntry>(`/food/meals/${encodeURIComponent(id)}/confirm`, { method: 'POST', body }),
    updateMeal: (id: string, body: Record<string, unknown>) => apiRequest<NutritionMealEntry>(`/food/meals/${encodeURIComponent(id)}`, { method: 'PATCH', body }),
    nutritionSummary: (patientId: number) => apiRequest<NutritionSummary>(`/patients/${patientId}/nutrition/summary`),
    addObservation: (patientId: number, body: Record<string, unknown>) => apiRequest(`/patients/${patientId}/nutrition/observations`, { method: 'POST', body }),
    updateProfile: (patientId: number, body: Record<string, unknown>) => apiRequest(`/patients/${patientId}/nutrition/profile`, { method: 'POST', body }),
  },
  access: {
    invitePatient: (email: string) => apiRequest('/patients/access-requests/invite', { method: 'POST', body: { email } }),
    approve: (patientId: number, doctorId: number) => apiRequest(`/patients/${patientId}/doctors/${doctorId}/approve-access`, { method: 'POST' }),
    decline: (patientId: number, doctorId: number) => apiRequest(`/patients/${patientId}/doctors/${doctorId}/decline-access`, { method: 'POST' }),
    revoke: (patientId: number, doctorId: number) => apiRequest(`/patients/${patientId}/doctors/${doctorId}/revoke`, { method: 'POST' }),
  },
} as const;

export function validateMRIFile(file: File): string | null {
  return /\.nii$/i.test(file.name) ? null : 'Select a NIfTI .nii file. Compressed and other formats are not accepted here.';
}
