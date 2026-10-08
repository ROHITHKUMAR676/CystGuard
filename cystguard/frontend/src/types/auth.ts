export type UserRole = 'DOCTOR' | 'PATIENT';
export interface CurrentUser { id: number; email: string; display_name: string | null; role: UserRole; doctor_access_code?: string | null; created_at: string }
export interface RegisterRequest { email: string; password: string; role: UserRole; display_name?: string; doctor_access_code?: string | null }
export interface LoginRequest { email: string; password: string }
export interface TokenResponse { access_token: string; token_type: 'bearer'; expires_in: number }
