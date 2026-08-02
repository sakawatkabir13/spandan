import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ApiResponse, Chamber, DoctorProfile, Schedule } from '../../types';
import { MainLayout } from '../../components/layout/MainLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { Alert } from '../../components/common/Alert';
import {
  Award,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  MapPin,
  Phone,
  Stethoscope,
} from 'lucide-react';

export const DoctorProfileDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [doctor, setDoctor] = useState<DoctorProfile | null>(null);
  const [chambers, setChambers] = useState<Chamber[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);

  // Booking modal state
  const [selectedSchedule, setSelectedSchedule] = useState<Schedule | null>(null);
  const [patientNote, setPatientNote] = useState('');
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookedResult, setBookedResult] = useState<any | null>(null);

  const fetchDoctorDetails = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [docResp, chamResp, schedResp] = await Promise.all([
        apiClient.get<ApiResponse<DoctorProfile>>(`/doctors/${id}`),
        apiClient.get<ApiResponse<Chamber[]>>(`/chambers/doctor/${id}`),
        apiClient.get<ApiResponse<Schedule[]>>(`/schedules/doctor/${id}`),
      ]);

      if (docResp.data.success) setDoctor(docResp.data.data);
      if (chamResp.data.success) setChambers(chamResp.data.data);
      if (schedResp.data.success) setSchedules(schedResp.data.data);
    } catch (err) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDoctorDetails();
  }, [id]);

  const handleOpenBookingModal = (schedule: Schedule) => {
    if (!isAuthenticated || !user) {
      navigate('/login');
      return;
    }
    if (user.role !== 'patient') {
      alert('Only registered patient accounts can book serials directly online.');
      return;
    }
    setSelectedSchedule(schedule);
    setBookingError(null);
    setBookedResult(null);
  };

  const handleConfirmBooking = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSchedule) return;
    setBookingLoading(true);
    setBookingError(null);

    try {
      const resp = await apiClient.post<ApiResponse<any>>('/appointments', {
        schedule_id: selectedSchedule.id,
        patient_note: patientNote || undefined,
        booking_source: 'online',
      });
      if (resp.data.success) {
        setBookedResult(resp.data.data);
        fetchDoctorDetails(); // refresh queue / schedule capacity
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Failed to book serial. Please try again.';
      setBookingError(msg);
    } finally {
      setBookingLoading(false);
    }
  };

  if (loading) return <MainLayout><LoadingSpinner size="lg" text="Loading doctor chamber details..." /></MainLayout>;
  if (!doctor) return <MainLayout><Alert type="error" message="Doctor profile not found." /></MainLayout>;

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Doctor Header Banner */}
        <div className="glass-card p-6 sm:p-8 border-slate-200 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-start gap-5">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-spandan-600 to-spandan-400 flex items-center justify-center text-white font-extrabold text-3xl shadow-lg shadow-spandan-500/25 flex-shrink-0">
              {doctor.user?.full_name ? doctor.user.full_name.split(' ').slice(-1)[0][0] : 'DR'}
            </div>

            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">{doctor.user?.full_name}</h1>
                {doctor.is_bmdc_verified && (
                  <Badge variant="success" className="flex items-center gap-1.5 px-3 py-1 text-xs">
                    <CheckCircle2 className="w-4 h-4" /> BMDC Verified ({doctor.medical_registration_number})
                  </Badge>
                )}
              </div>

              <p className="text-base font-semibold text-spandan-700">
                {doctor.specialization?.name || 'General Practitioner'}
              </p>

              <div className="flex flex-wrap items-center gap-6 text-sm text-slate-600 pt-1">
                {doctor.current_workplace && (
                  <span className="flex items-center gap-1.5">
                    <Building2 className="w-4 h-4 text-slate-400" />
                    {doctor.current_workplace}
                  </span>
                )}
                <span className="flex items-center gap-1.5">
                  <Award className="w-4 h-4 text-slate-400" />
                  <strong>{doctor.years_of_experience}</strong> years clinical experience
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Qualifications & Biography */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="md:col-span-2 space-y-6">
            <div className="glass-card p-6 border-slate-200">
              <h3 className="font-bold text-lg text-slate-900 mb-3 flex items-center gap-2">
                <Stethoscope className="w-5 h-5 text-spandan-600" /> Biography & Clinical Profile
              </h3>
              <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">
                {doctor.biography ||
                  `${doctor.user?.full_name} is a highly experienced ${doctor.specialization?.name || 'medical specialist'} practicing in private chambers with over ${doctor.years_of_experience} years of expertise. Dedicated to patient-centric care and accurate diagnosis.`}
              </p>

              {doctor.qualifications && doctor.qualifications.length > 0 && (
                <div className="mt-6 pt-6 border-t border-slate-100">
                  <h4 className="font-semibold text-sm text-slate-800 uppercase tracking-wider mb-3">
                    Academic & Professional Degrees
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {doctor.qualifications.map((q) => (
                      <div
                        key={q.id}
                        className="bg-slate-100 border border-slate-200 px-3 py-1.5 rounded-xl text-xs font-medium text-slate-800"
                      >
                        <strong className="text-spandan-800">{q.degree_name}</strong> - {q.institution} ({q.passing_year})
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Available Schedules / Book Serial */}
            <div className="glass-card p-6 border-slate-200">
              <h3 className="font-bold text-lg text-slate-900 mb-4 flex items-center gap-2">
                <Calendar className="w-5 h-5 text-spandan-600" /> Available Consultation Schedules
              </h3>

              {schedules.length === 0 ? (
                <p className="text-sm text-slate-500 italic py-4">
                  No upcoming open schedules listed for this doctor currently.
                </p>
              ) : (
                <div className="space-y-4">
                  {schedules.map((sched) => {
                    const chamber = chambers.find((c) => c.id === sched.chamber_id) || sched.chamber;
                    const isOpen = sched.status === 'open';
                    return (
                      <div
                        key={sched.id}
                        className="border border-slate-200 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white/50 hover:bg-white transition"
                      >
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900 text-base">
                              {new Date(sched.schedule_date).toLocaleDateString('en-GB', {
                                weekday: 'short',
                                day: 'numeric',
                                month: 'short',
                                year: 'numeric',
                              })}
                            </span>
                            <Badge
                              variant={isOpen ? 'success' : sched.status === 'full' ? 'warning' : 'neutral'}
                            >
                              {sched.status.toUpperCase()}
                            </Badge>
                          </div>

                          <div className="flex flex-wrap items-center gap-4 text-xs font-medium text-slate-600">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5 text-spandan-600" />
                              {sched.start_time.slice(0, 5)} - {sched.end_time.slice(0, 5)}
                            </span>
                            {chamber && (
                              <span className="flex items-center gap-1">
                                <MapPin className="w-3.5 h-3.5 text-spandan-600" />
                                {chamber.name} ({chamber.area})
                              </span>
                            )}
                            <span>
                              Max Patients: <strong className="text-slate-800">{sched.maximum_patients}</strong>
                            </span>
                          </div>

                          {sched.queue_state && (
                            <div className="text-xs text-emerald-700 font-semibold bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200 inline-block">
                              Live Queue: Running Serial #{sched.queue_state.current_serial}{' '}
                              {sched.queue_state.delay_minutes > 0 &&
                                `(${sched.queue_state.delay_minutes} mins delay)`}
                            </div>
                          )}
                        </div>

                        <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2">
                          {chamber && (
                            <span className="text-sm font-bold text-slate-900">৳{chamber.consultation_fee}</span>
                          )}
                          <button
                            disabled={!isOpen}
                            onClick={() => handleOpenBookingModal(sched)}
                            className="btn-primary py-2 px-4 text-xs font-semibold"
                          >
                            {isOpen ? 'Book Serial' : 'Schedule Full'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Chambers List Sidebar */}
          <div className="space-y-6">
            <div className="glass-card p-6 border-slate-200 space-y-4">
              <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                <MapPin className="w-5 h-5 text-spandan-600" /> Chambers & Locations
              </h3>

              {chambers.length === 0 ? (
                <p className="text-xs text-slate-500">No active chambers found.</p>
              ) : (
                chambers.map((c) => (
                  <div key={c.id} className="border-b border-slate-100 last:border-b-0 pb-4 last:pb-0 space-y-1.5">
                    <h4 className="font-bold text-sm text-slate-900">{c.name}</h4>
                    <p className="text-xs text-slate-600">{c.address}</p>
                    <p className="text-xs text-slate-500 font-medium">
                      {c.area}, {c.district}
                    </p>
                    {c.phone_number && (
                      <p className="text-xs text-spandan-700 flex items-center gap-1 font-semibold pt-1">
                        <Phone className="w-3 h-3" /> {c.phone_number}
                      </p>
                    )}
                    <div className="flex items-center justify-between text-xs pt-1">
                      <span className="text-slate-500">New Patient: <strong>৳{c.consultation_fee}</strong></span>
                      {c.follow_up_fee && (
                        <span className="text-slate-500">Follow-up: <strong>৳{c.follow_up_fee}</strong></span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Book Serial Modal */}
        <Modal
          isOpen={!!selectedSchedule}
          onClose={() => setSelectedSchedule(null)}
          title="Confirm Serial Booking"
        >
          {bookedResult ? (
            <div className="text-center space-y-4 py-4 animate-fade-in">
              <div className="w-16 h-16 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto shadow-inner">
                <CheckCircle2 className="w-10 h-10" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900">Booking Confirmed!</h3>
              <div className="bg-spandan-50 p-4 rounded-2xl border border-spandan-200 text-slate-800 space-y-2">
                <p className="text-sm font-medium">Your assigned serial number is:</p>
                <div className="text-4xl font-extrabold text-spandan-700">#{bookedResult.serial_number}</div>
                {bookedResult.estimated_consultation_at && (
                  <p className="text-xs text-slate-600 pt-1">
                    Estimated Time:{' '}
                    <strong>
                      {new Date(bookedResult.estimated_consultation_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </strong>
                  </p>
                )}
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                You can track running serial numbers live from your Patient Dashboard right before leaving home.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setSelectedSchedule(null)}
                  className="btn-secondary flex-1 py-2.5 text-xs font-semibold"
                >
                  Close
                </button>
                <Link
                  to="/dashboard/patient"
                  className="btn-primary flex-1 py-2.5 text-xs font-semibold"
                >
                  View My Dashboard
                </Link>
              </div>
            </div>
          ) : selectedSchedule ? (
            <form onSubmit={handleConfirmBooking} className="space-y-4">
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-500">Doctor:</span>
                  <strong className="text-slate-800">{doctor.user?.full_name}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Date:</span>
                  <strong className="text-slate-800">
                    {new Date(selectedSchedule.schedule_date).toLocaleDateString('en-GB')}
                  </strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Time:</span>
                  <strong className="text-slate-800">
                    {selectedSchedule.start_time.slice(0, 5)} - {selectedSchedule.end_time.slice(0, 5)}
                  </strong>
                </div>
              </div>

              {bookingError && <Alert type="error" message={bookingError} />}

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Brief Note for Doctor / Symptoms (Optional)
                </label>
                <textarea
                  rows={3}
                  placeholder="e.g. Chronic headache, high blood pressure checkup..."
                  value={patientNote}
                  onChange={(e) => setPatientNote(e.target.value)}
                  className="input-field bg-white"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setSelectedSchedule(null)}
                  className="btn-secondary py-2 px-4 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={bookingLoading}
                  className="btn-primary py-2 px-5 text-xs font-semibold"
                >
                  {bookingLoading ? 'Assigning Serial...' : 'Confirm & Get Serial Number'}
                </button>
              </div>
            </form>
          ) : null}
        </Modal>
      </div>
    </MainLayout>
  );
};
