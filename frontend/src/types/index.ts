export type UserRole = 'patient' | 'doctor' | 'assistant' | 'administrator';

export interface User {
  id: string;
  email: string;
  phone_number: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  profile_picture_url?: string | null;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  timestamp: string;
}

export interface PatientProfile {
  id: string;
  user_id: string;
  date_of_birth?: string | null;
  gender?: string | null;
  blood_group?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  medical_history_summary?: string | null;
  allergies?: string | null;
  created_at: string;
  updated_at: string;
  user?: User;
}

export interface Specialization {
  id: string;
  name: string;
  description?: string | null;
  icon_url?: string | null;
  is_active: boolean;
}

export interface Qualification {
  id: string;
  doctor_id: string;
  degree_name: string;
  institution: string;
  passing_year: number;
  country: string;
}

export interface DoctorProfile {
  id: string;
  user_id: string;
  medical_registration_number: string;
  specialization_id?: string | null;
  current_workplace?: string | null;
  years_of_experience: number;
  biography?: string | null;
  consultation_fee_default?: number | null;
  is_bmdc_verified: boolean;
  created_at: string;
  updated_at: string;
  user?: User;
  specialization?: Specialization | null;
  qualifications: Qualification[];
  chambers?: Chamber[];
}

export interface Chamber {
  id: string;
  doctor_id: string;
  name: string;
  address: string;
  district: string;
  area: string;
  phone_number?: string | null;
  consultation_fee: number;
  follow_up_fee?: number | null;
  average_consultation_minutes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  doctor?: DoctorProfile;
}

export type ScheduleStatus = 'open' | 'full' | 'closed' | 'cancelled';

export interface QueueState {
  id: string;
  schedule_id: string;
  current_serial: number;
  delay_minutes: number;
  status_message?: string | null;
  updated_at: string;
}

export interface Schedule {
  id: string;
  doctor_id: string;
  chamber_id: string;
  schedule_date: string;
  start_time: string;
  end_time: string;
  maximum_patients: number;
  booked_count?: number;
  status: ScheduleStatus;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  chamber?: Chamber;
  queue_state?: QueueState | null;
}

export type AppointmentStatus =
  | 'booked'
  | 'confirmed'
  | 'checked_in'
  | 'in_consultation'
  | 'completed'
  | 'cancelled'
  | 'no_show';

export type BookingSource = 'online' | 'walk_in' | 'phone_assistant';

export interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  chamber_id: string;
  schedule_id: string;
  serial_number: number;
  booking_source: BookingSource;
  appointment_status: AppointmentStatus;
  estimated_consultation_at?: string | null;
  actual_consultation_started_at?: string | null;
  actual_consultation_completed_at?: string | null;
  patient_note?: string | null;
  cancellation_reason?: string | null;
  booked_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
  cancelled_at?: string | null;
  doctor?: DoctorProfile;
  chamber?: Chamber;
  schedule?: Schedule;
  patient?: PatientProfile;
}

export interface SerialTrackingInfo {
  schedule_id: string;
  current_serial_running: number;
  delay_minutes: number;
  status_message?: string | null;
  your_serial_number?: number | null;
  people_ahead?: number | null;
  estimated_waiting_minutes?: number | null;
  estimated_consultation_time?: string | null;
}

export type UrgencyLevel = 'routine' | 'soon' | 'urgent' | 'emergency';

export interface SpecialistRecommendation {
  id: string;
  patient_id?: string | null;
  symptoms_text: string;
  recommended_specialization_id?: string | null;
  recommended_specialization_name: string;
  alternative_specialization_name?: string | null;
  urgency_level: UrgencyLevel;
  reasoning_summary: string;
  safety_message?: string | null;
  disclaimer: string;
  model_identifier?: string | null;
  created_at: string;
}
