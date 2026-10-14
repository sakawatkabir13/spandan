import { useLanguage } from '../../context/LanguageContext';
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { ApiResponse, Appointment, SerialTrackingInfo } from '../../types';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { useLiveQueue } from '../../hooks/useLiveQueue';
import { AppointmentActions, AppointmentPaymentAction } from '../../components/common/AppointmentActions';
import { Activity, Calendar, Check, Clock, CreditCard, FileHeart, MapPin, Plus, RefreshCw } from 'lucide-react';

type BillingSummary = { id: string; amount: number; currency: string; payment_status: string };
const finished = (app: Appointment) => ['cancelled', 'completed', 'absent'].includes(app.appointment_status);
const statusLabels: Record<string, string> = { booked: 'Booked', confirmed: 'Attendance confirmed', checked_in: 'Checked in', in_consultation: 'In consultation', completed: 'Completed', cancelled: 'Cancelled', absent: 'Missed appointment', skipped: 'Skipped', waiting: 'Waiting' };
const paymentLabels: Record<string, string> = { paid: 'Paid', pending: 'Awaiting payment', refunded: 'Refunded', refund_pending: 'Refund processing', unpaid: 'Unpaid' };

export const PatientDashboard: React.FC = () => {
  const { t } = useLanguage();
  const [loadError, setLoadError] = useState('');
  const [medicalCompletion, setMedicalCompletion] = useState<number | null>(null);
  const [billing, setBilling] = useState<Record<string, BillingSummary>>({});
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'upcoming' | 'history' | 'all'>('upcoming');
  const [trackingMap, setTrackingMap] = useState<Record<string, SerialTrackingInfo>>({});
  const [refreshing, setRefreshing] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelError, setCancelError] = useState('');
  const [cancelLoading, setCancelLoading] = useState(false);
  const fetchAllTracking = useCallback(async (apps: Appointment[]) => {
    const results = await Promise.allSettled(apps.filter(app => !finished(app)).map(async app => {
      const response = await apiClient.get<ApiResponse<SerialTrackingInfo>>(`/appointments/track/${app.schedule_id}?appointment_id=${app.id}`);
      return [app.id, response.data.data] as const;
    }));
    setTrackingMap(Object.fromEntries(results.flatMap(result => result.status === 'fulfilled' ? [result.value] : [])));
  }, []);
  const fetchAppointments = useCallback(async (initial = false) => {
    if (initial) setLoading(true);
    try {
      const response = await apiClient.get<ApiResponse<Appointment[]>>('/appointments/me');
      setAppointments(response.data.data);
      setLoadError('');
      if (initial && response.data.data.length && response.data.data.every(finished)) setFilter('history');
      await Promise.all([
        fetchAllTracking(response.data.data),
        apiClient.get<ApiResponse<BillingSummary[]>>('/payments/appointments').then(result => setBilling(Object.fromEntries(result.data.data.map(row => [row.id, row])))).catch(() => setBilling({})),
      ]);
    } catch (error) { setLoadError(errorMessage(error)); }
    finally { setLoading(false); }
  }, [fetchAllTracking]);
  const liveSchedule = appointments.find(app => !finished(app))?.schedule_id;
  const live = useLiveQueue(liveSchedule, () => fetchAppointments());
  useEffect(() => {
    void fetchAppointments(true);
    void apiClient.get('/medical-records/me').then(response => setMedicalCompletion(response.data.data.completion.percent)).catch(() => {});
    const timer = window.setInterval(() => { if (!document.hidden) void fetchAppointments(); }, 15000);
    return () => window.clearInterval(timer);
  }, [fetchAppointments]);
  const refresh = async () => { setRefreshing(true); try { await fetchAppointments(); } finally { setRefreshing(false); } };
  const cancel = async (event: React.FormEvent) => {
    event.preventDefault(); if (!cancelTarget) return;
    setCancelLoading(true); setCancelError('');
    try {
      await apiClient.patch(`/appointments/${cancelTarget.id}/status`, { appointment_status: 'cancelled', cancellation_reason: cancelReason.trim() });
      setCancelTarget(null); setCancelReason(''); await fetchAppointments();
    } catch (error) { setCancelError(errorMessage(error)); }
    finally { setCancelLoading(false); }
  };
  const confirm = async (id: string) => {
    setConfirming(id);
    try { await apiClient.patch(`/appointments/${id}/status`, { appointment_status: 'confirmed' }); await fetchAppointments(); }
    catch (error) { setLoadError(errorMessage(error)); }
    finally { setConfirming(null); }
  };
  const upcoming = appointments.filter(app => !finished(app));
  const history = appointments.filter(finished);
  const visible = (filter === 'upcoming' ? upcoming : filter === 'history' ? history : appointments).slice().sort((a, b) => {
    const first = `${a.schedule?.schedule_date || ''}T${a.schedule?.start_time || ''}`;
    const second = `${b.schedule?.schedule_date || ''}T${b.schedule?.start_time || ''}`;
    return filter === 'upcoming' ? first.localeCompare(second) : second.localeCompare(first);
  });
  return <DashboardLayout><div className="space-y-6">
    <header className="flex flex-col xl:flex-row xl:items-start justify-between gap-4">
      <div className="min-w-0"><h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{t('My appointments')}</h1><p className="text-sm text-slate-600 mt-2">Manage visits, track your serial, and pay consultation fees.</p></div>
      <div className="flex flex-wrap gap-2"><Link className="btn-secondary text-sm" to="/dashboard/patient/payments"><CreditCard className="h-4 w-4" />Payments</Link><Link className="btn-primary text-sm" to="/doctors?view=booking"><Plus className="h-4 w-4" />Book appointment</Link></div>
    </header>
    {medicalCompletion !== null && medicalCompletion < 100 && <section className="rounded-2xl border border-spandan-200 bg-spandan-50 p-4 flex items-start gap-3"><FileHeart className="h-5 w-5 shrink-0 text-spandan-700 mt-0.5" /><div className="min-w-0 text-sm"><h2 className="font-semibold text-spandan-950">Health profile · {medicalCompletion}% complete</h2><p className="text-slate-600 mt-1">Add your medical history and reports before your visit.</p><Link className="inline-flex min-h-9 items-center font-semibold text-spandan-700 underline underline-offset-2" to="/dashboard/patient/profile#medical-records">Update medical profile</Link></div></section>}
    {loadError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800 text-sm flex flex-wrap items-center gap-3"><span className="flex-1">{loadError}</span><button className="underline font-semibold" disabled={refreshing} onClick={() => void refresh()}>Try again</button></div>}
    <section aria-label="Your appointments" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Filter appointments" className="inline-flex max-w-full rounded-xl border border-slate-200 bg-white p-1 gap-1">{(['upcoming', 'history', 'all'] as const).map(name => <button key={name} onClick={() => setFilter(name)} aria-pressed={filter === name} className={`rounded-lg px-3 py-2 text-sm font-medium capitalize min-h-10 ${filter === name ? 'bg-spandan-50 text-spandan-800' : 'text-slate-500 hover:bg-slate-50'}`}>{t(name.charAt(0).toUpperCase() + name.slice(1))} <span className="ml-1 text-xs">{name === 'upcoming' ? upcoming.length : name === 'history' ? history.length : appointments.length}</span></button>)}</nav>
        <button onClick={() => void refresh()} disabled={refreshing || loading} className="btn-secondary text-sm px-3" aria-label="Refresh appointments"><RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} /><span className="hidden sm:inline">{refreshing ? 'Refreshing…' : 'Refresh'}</span></button>
      </div>
      {liveSchedule && <p className="flex items-center gap-2 text-xs text-slate-500"><span className={`h-2 w-2 rounded-full ${live.connected ? 'bg-spandan-500' : 'bg-slate-400'}`} />{live.connected ? 'Queue updates are live' : 'Queue updates refresh automatically every 15 seconds'}</p>}
      {loading ? <LoadingSpinner size="lg" text="Loading your appointments…" /> : !visible.length ? <div className="glass-card px-5 py-12 text-center space-y-4"><Calendar className="h-10 w-10 text-spandan-500 mx-auto" /><h2 className="font-semibold text-lg">{appointments.length ? `No ${filter === 'upcoming' ? 'upcoming visits' : 'past appointments'} to show` : 'Your next visit starts here'}</h2><p className="text-sm text-slate-500 max-w-md mx-auto">{appointments.length ? 'Switch the appointment filter to see your other visits.' : 'Find a doctor and choose a chamber session. Your booking, payment, and queue updates will appear here.'}</p><div className="flex flex-wrap justify-center gap-3"><Link to="/doctors?view=booking" className="btn-primary text-sm">Find a doctor</Link>{!!appointments.length && <button className="btn-secondary text-sm" onClick={() => setFilter('all')}>View all appointments</button>}</div></div> : visible.map(app => {
        const tracking = trackingMap[app.id];
        const summary = billing[app.id];
        const closed = finished(app);
        const canCancel = !closed && app.appointment_status !== 'in_consultation';
        const amount = Number(summary?.amount ?? app.chamber?.consultation_fee ?? 0);
        return <article key={app.id} aria-labelledby={`appointment-${app.id}`} className="glass-card overflow-hidden border-slate-200" data-testid="appointment-card">
          <div className="p-4 sm:p-6 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_16rem] gap-5">
            <div className="min-w-0 space-y-4">
              <div className="flex flex-wrap items-center gap-2"><span className="rounded-lg bg-spandan-50 px-2.5 py-1 text-sm font-semibold text-spandan-800">Serial #{app.serial_number}</span><Badge variant={app.appointment_status === 'cancelled' ? 'neutral' : closed ? 'info' : 'success'}>{statusLabels[app.appointment_status] || app.appointment_status.replaceAll('_', ' ')}</Badge></div>
              <div><h2 id={`appointment-${app.id}`} className="text-lg sm:text-xl font-bold">{app.doctor?.full_name || 'Doctor consultation'}</h2><p className="text-sm text-spandan-700 mt-1">{app.doctor?.specializations.map(s => s.name).join(', ') || 'Medical specialist'}</p></div>
              <dl className="space-y-3 text-sm"><div className="flex items-start gap-2.5"><Calendar className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" /><div><dt className="sr-only">Session date and time</dt><dd className="font-medium">{app.schedule ? new Date(app.schedule.schedule_date + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : 'Date to be confirmed'}<span className="block text-slate-500 font-normal">{app.schedule?.start_time.slice(0, 5)} – {app.schedule?.end_time.slice(0, 5)} · Dhaka time</span></dd></div></div>
                {app.chamber && <div className="flex items-start gap-2.5"><MapPin className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" /><div><dt className="sr-only">Chamber</dt><dd>{app.chamber.name}<span className="block text-slate-500">{[app.chamber.area, app.chamber.district].filter(Boolean).join(', ')}</span></dd></div></div>}
                {app.attendee_name && <div><dt className="inline text-slate-500">Patient: </dt><dd className="inline font-medium">{app.attendee_name}</dd></div>}
              </dl>
              {app.patient_note && <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-600"><span className="font-medium">Your note: </span>{app.patient_note}</p>}
              {app.appointment_status === 'cancelled' && <p className="text-sm text-slate-500">Cancellation reason: {app.cancellation_reason || 'Cancelled'}</p>}
            </div>
            <div className="min-w-0 space-y-3">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span className="text-slate-500">Consultation fee</span><strong>৳{amount.toLocaleString('en-BD')}</strong></div><p className="text-xs text-slate-500 mt-2">Payment: <span className={summary?.payment_status === 'paid' ? 'font-semibold text-spandan-700' : 'font-medium text-slate-700'}>{paymentLabels[summary?.payment_status] || 'Check payment details'}</span></p></div>
              <AppointmentPaymentAction appointment={app} paymentStatus={summary?.payment_status} fee={amount} />
              {!closed && <div className="rounded-xl border border-spandan-100 bg-spandan-50/60 p-4 space-y-3"><h3 className="flex items-center gap-2 text-sm font-semibold text-spandan-900"><Activity className="h-4 w-4 shrink-0" />Queue status</h3>{tracking ? <><dl className="grid grid-cols-2 gap-3"><div><dt className="text-xs text-slate-500">Running serial</dt><dd className="mt-1 text-2xl font-bold text-spandan-800">#{tracking.current_serial_running}</dd></div><div><dt className="text-xs text-slate-500">People ahead</dt><dd className="mt-1 text-2xl font-bold">{tracking.people_ahead ?? '—'}</dd></div></dl>{tracking.delay_minutes > 0 && <p className="text-xs text-amber-800">Session delayed by {tracking.delay_minutes} minutes</p>}{tracking.estimated_consultation_time && <p className="text-xs text-slate-600 flex items-start gap-1.5"><Clock className="h-3.5 w-3.5 shrink-0 mt-0.5" /><span>Estimated: {new Date(tracking.estimated_consultation_time).toLocaleString('en-GB', { timeZone: 'Asia/Dhaka', dateStyle: 'medium', timeStyle: 'short' })}. Times may change.</span></p>}<p className="text-xs text-slate-500">{tracking.status_message || 'Follow your serial here before travelling.'}</p></> : <p className="text-sm text-slate-600">Live queue information is temporarily unavailable. Refresh to try again.</p>}</div>}
            </div>
          </div>
          <div className="border-t border-slate-100 px-4 py-4 sm:px-6 flex flex-col gap-3">
            <AppointmentActions appointment={app} updated={() => void fetchAppointments()} />
            {canCancel && <div className="flex flex-wrap gap-2 items-center">{app.appointment_status === 'booked' && <button disabled={confirming === app.id} onClick={() => void confirm(app.id)} className="btn-secondary text-sm"><Check className="h-4 w-4" />{confirming === app.id ? 'Confirming…' : t('Confirm attendance')}</button>}<button onClick={() => { setCancelError(''); setCancelReason(''); setCancelTarget(app); }} className="min-h-11 px-3 text-sm font-medium text-red-600 hover:bg-red-50 rounded-xl">Cancel booking</button></div>}
          </div>
        </article>;
      })}
    </section>
    <Modal isOpen={!!cancelTarget} onClose={() => { if (!cancelLoading) setCancelTarget(null); }} title="Cancel appointment">
      {cancelTarget && <form onSubmit={cancel} className="space-y-4"><p className="text-sm text-slate-600">Cancel serial #{cancelTarget.serial_number} with {cancelTarget.doctor?.full_name || 'your doctor'}? Your place will become available to another patient.</p>{cancelError && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{cancelError}</p>}<label className="block text-sm font-medium">Reason for cancellation<input aria-label="Cancellation reason" required maxLength={500} value={cancelReason} onChange={event => setCancelReason(event.target.value)} className="input-field mt-2" placeholder="Tell us why you need to cancel" /></label><div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 border-t pt-4"><button type="button" disabled={cancelLoading} onClick={() => setCancelTarget(null)} className="btn-secondary text-sm">{t('Keep Appointment')}</button><button disabled={cancelLoading || !cancelReason.trim()} className="btn-danger text-sm">{cancelLoading ? 'Cancelling…' : t('Yes, Cancel Serial')}</button></div></form>}
    </Modal>
  </div></DashboardLayout>;
};
