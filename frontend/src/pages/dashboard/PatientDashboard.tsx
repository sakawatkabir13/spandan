import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ApiResponse, Appointment, SerialTrackingInfo } from '../../types';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import {
  Activity,
  Calendar,
  MapPin,
  RefreshCw,
} from 'lucide-react';

export const PatientDashboard: React.FC = () => {
  const [loadError, setLoadError] = useState('');
  useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  // Live tracking details map keyed by schedule_id
  const [trackingMap, setTrackingMap] = useState<Record<string, SerialTrackingInfo>>({});
  const [refreshing, setRefreshing] = useState(false);

  // Cancel modal
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelLoading, setCancelLoading] = useState(false);

  const fetchAppointments = async () => {
    setLoading(true);
    try {
      const resp = await apiClient.get<ApiResponse<Appointment[]>>('/appointments/me');
      if (resp.data.success) {
        setAppointments(resp.data.data);
        await fetchAllTracking(resp.data.data);
      }
    } catch (err) {
      setLoadError('Unable to load the latest data. Please refresh to try again.');
    } finally {
      setLoading(false);
    }
  };

  const fetchAllTracking = async (apps: Appointment[]) => {
    const activeApps = apps.filter(
      (a) => a.appointment_status !== 'cancelled' && a.appointment_status !== 'completed' && a.appointment_status !== 'absent'
    );
    const newMap: Record<string, SerialTrackingInfo> = {};

    await Promise.all(
      activeApps.map(async (app) => {
        try {
          const tResp = await apiClient.get<ApiResponse<SerialTrackingInfo>>(
            `/appointments/track/${app.schedule_id}`
          );
          if (tResp.data.success) {
            newMap[app.schedule_id] = tResp.data.data;
          }
        } catch (e) {
          setLoadError('Unable to load the latest data. Please refresh to try again.');
        }
      })
    );
    setTrackingMap(newMap);
  };

  const handleRefreshTracking = async () => {
    setRefreshing(true);
    await fetchAllTracking(appointments);
    setRefreshing(false);
  };

  useEffect(() => {
    fetchAppointments();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => { if (!document.hidden) void fetchAllTracking(appointments); }, 15000);
    return () => window.clearInterval(timer);
  }, [appointments]);

  const handleConfirmCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelTarget) return;
    setCancelLoading(true);

    try {
      await apiClient.patch(`/appointments/${cancelTarget.id}/status`, {
        appointment_status: 'cancelled',
        cancellation_reason: cancelReason || 'Cancelled by patient',
      });
      setCancelTarget(null);
      setCancelReason('');
      fetchAppointments();
    } catch (err) {
      alert('Failed to cancel appointment. Please try again.');
    } finally {
      setCancelLoading(false);
    }
  };

  const handleConfirmAttendance = async (appointmentId: string) => {
    try {
      await apiClient.patch(`/appointments/${appointmentId}/status`, {
        appointment_status: 'confirmed',
      });
      setLoadError('');
      await fetchAppointments();
    } catch (error: any) {
      setLoadError(error.response?.data?.error?.message || 'Unable to confirm attendance.');
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {loadError && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{loadError}</p>}
        {/* Header */}
        <div className="glass-card p-6 border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">My Appointments & Live Serials</h1>
            <p className="text-sm text-slate-600">
              Track real-time chamber queue progress right from home before departing.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleRefreshTracking}
              disabled={refreshing}
              className="btn-secondary py-2 px-4 text-xs font-semibold"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh Serials
            </button>
            <Link to="/doctors" className="btn-primary py-2 px-4 text-xs font-semibold">
              + Book New Serial
            </Link>
          </div>
        </div>

        {loading ? (
          <LoadingSpinner size="lg" text="Loading your booked serials..." />
        ) : appointments.length === 0 ? (
          <div className="glass-card p-12 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mx-auto">
              <Calendar className="w-8 h-8" />
            </div>
            <h3 className="font-semibold text-lg text-slate-800">You have no booked appointments yet</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              Search verified doctor chambers and book your serial online to track live queue numbers right from here.
            </p>
            <div className="flex justify-center gap-3 pt-2">
              <Link to="/doctors" className="btn-primary text-sm">
                Find Doctors Now
              </Link>
              <Link to="/ai-triage" className="btn-secondary text-sm">
                AI Symptom Checker
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {appointments.map((app) => {
              const tracking = trackingMap[app.schedule_id];
              const isCancelled = app.appointment_status === 'cancelled';
              const isCompleted = app.appointment_status === 'completed' || app.appointment_status === 'absent';
              const canCancel = !isCancelled && !isCompleted && app.appointment_status !== 'in_consultation';

              return (
                <div
                  key={app.id}
                  className={`glass-card p-6 border transition flex flex-col lg:flex-row items-stretch justify-between gap-6 ${
                    isCancelled
                      ? 'bg-slate-50/60 border-slate-200 opacity-75'
                      : 'border-slate-200/90 shadow-md hover:shadow-lg'
                  }`}
                >
                  {/* Left Column: Doctor & Schedule Info */}
                  <div className="space-y-3 flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-xs font-bold uppercase tracking-wider text-spandan-700 bg-spandan-50 border border-spandan-200 px-2.5 py-0.5 rounded-full">
                        Serial #{app.serial_number}
                      </span>
                      <Badge
                        variant={
                          app.appointment_status === 'in_consultation'
                            ? 'primary'
                            : app.appointment_status === 'checked_in'
                            ? 'info'
                            : isCancelled
                            ? 'danger'
                            : isCompleted
                            ? 'neutral'
                            : 'success'
                        }
                      >
                        {app.appointment_status.replace('_', ' ').toUpperCase()}
                      </Badge>
                      <span className="text-xs text-slate-400">
                        Booked on {new Date(app.created_at).toLocaleDateString('en-GB')}
                      </span>
                    </div>

                    <h3 className="text-xl font-bold text-slate-900">
                      {app.doctor?.full_name || 'Doctor Consultation'}
                    </h3>
                    <p className="text-sm font-semibold text-spandan-700">
                      {app.doctor?.specializations.map((s) => s.name).join(', ') || 'Medical Specialist'}
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-600 pt-1">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-spandan-600" />
                        <span>
                          <strong>
                            {app.schedule &&
                              new Date(app.schedule.schedule_date).toLocaleDateString('en-GB', {
                                weekday: 'short',
                                day: 'numeric',
                                month: 'short',
                              })}
                          </strong>{' '}
                          ({app.schedule?.start_time.slice(0, 5)} - {app.schedule?.end_time.slice(0, 5)})
                        </span>
                      </div>

                      {app.chamber && (
                        <div className="flex items-center gap-2">
                          <MapPin className="w-4 h-4 text-spandan-600" />
                          <span>
                            <strong>{app.chamber.name}</strong> ({app.chamber.area})
                          </span>
                        </div>
                      )}
                    </div>

                    {app.patient_note && (
                      <div className="text-xs text-slate-600 bg-slate-100/80 p-2.5 rounded-xl italic mt-2">
                        "Your note: {app.patient_note}"
                      </div>
                    )}
                  </div>

                  {/* Right Column: Live Serial Tracker Widget */}
                  {!isCancelled && !isCompleted && tracking ? (
                    <div className="bg-gradient-to-br from-slate-900 to-spandan-950 text-white p-5 rounded-2xl flex flex-col justify-between min-w-[280px] sm:min-w-[320px] shadow-lg border border-slate-800">
                      <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-xs">
                        <span className="font-semibold text-spandan-300 flex items-center gap-1.5">
                          <Activity className="w-4 h-4 text-emerald-400 animate-pulse" /> Live Queue Status
                        </span>
                        {tracking.delay_minutes > 0 && (
                          <span className="bg-amber-500/20 text-amber-300 text-[10px] font-bold px-2 py-0.5 rounded">
                            +{tracking.delay_minutes}m delay
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-3 py-3 text-center">
                        <div className="bg-white/5 rounded-xl p-2.5 border border-white/10">
                          <span className="text-[10px] text-slate-400 uppercase block font-medium">Running Serial</span>
                          <span className="text-2xl font-black text-emerald-400">
                            #{tracking.current_serial_running}
                          </span>
                        </div>
                        <div className="bg-white/5 rounded-xl p-2.5 border border-white/10">
                          <span className="text-[10px] text-slate-400 uppercase block font-medium">People Ahead</span>
                          <span className="text-2xl font-black text-white">
                            {tracking.people_ahead ?? '—'}
                          </span>
                        </div>
                      </div>

                      {tracking.estimated_consultation_time && <p className="text-xs text-slate-300">Estimated consultation: {new Date(tracking.estimated_consultation_time).toLocaleString('en-GB', { timeZone: 'Asia/Dhaka', dateStyle: 'medium', timeStyle: 'short' })} (Dhaka). Times may change.</p>}
                      <div className="pt-2 text-[11px] text-slate-300 flex items-center justify-between">
                        <span>{tracking.status_message || 'Queue ongoing'}</span>
                        <span className="flex items-center gap-3 ml-2">
                          {app.appointment_status === 'booked' && (
                            <button
                              onClick={() => void handleConfirmAttendance(app.id)}
                              className="text-emerald-300 hover:text-emerald-200 underline font-semibold"
                            >
                              Confirm attendance
                            </button>
                          )}
                          <button
                            disabled={!canCancel}
                            onClick={() => setCancelTarget(app)}
                            className="text-red-400 hover:text-red-300 underline font-semibold"
                          >
                            Cancel Serial
                          </button>
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col justify-end items-start lg:items-end gap-2 self-center">
                      {isCancelled && (
                        <span className="text-xs text-red-600 font-medium italic">
                          Reason: {app.cancellation_reason || 'Cancelled'}
                        </span>
                      )}
                      {canCancel && (
                        <div className="flex gap-2">
                          {app.appointment_status === 'booked' && (
                            <button
                              onClick={() => void handleConfirmAttendance(app.id)}
                              className="btn-secondary py-2 px-4 text-xs font-semibold text-emerald-700 hover:bg-emerald-50"
                            >
                              Confirm Attendance
                            </button>
                          )}
                          <button
                            disabled={!canCancel}
                            onClick={() => setCancelTarget(app)}
                            className="btn-secondary py-2 px-4 text-xs font-semibold text-red-600 hover:bg-red-50"
                          >
                            Cancel Booking
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Cancellation Modal */}
        <Modal
          isOpen={!!cancelTarget}
          onClose={() => setCancelTarget(null)}
          title="Cancel Appointment Serial"
        >
          {cancelTarget && (
            <form onSubmit={handleConfirmCancel} className="space-y-4">
              <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs space-y-1">
                <p className="font-bold">Are you sure you want to cancel Serial #{cancelTarget.serial_number}?</p>
                <p>This slot will be reopened immediately for other waiting patients.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Reason for Cancellation
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Schedule conflict, feeling better..."
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="input-field bg-white"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setCancelTarget(null)}
                  className="btn-secondary py-2 px-4 text-xs font-semibold"
                >
                  Keep Appointment
                </button>
                <button
                  type="submit"
                  disabled={cancelLoading}
                  className="btn-danger py-2 px-5 text-xs font-semibold"
                >
                  {cancelLoading ? 'Cancelling...' : 'Yes, Cancel Serial'}
                </button>
              </div>
            </form>
          )}
        </Modal>
      </div>
    </DashboardLayout>
  );
};
