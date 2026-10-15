import { I18nText } from '../../context/LanguageContext';
import { useLanguage } from '../../context/LanguageContext';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarClock, CreditCard, Download, Receipt, Video } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { Appointment, Schedule } from '../../types';
import { Modal } from './Modal';

export function AppointmentPaymentAction({ appointment, paymentStatus, fee = 0 }: { appointment: Appointment; paymentStatus?: string; fee?: number }) {
  const { t } = useLanguage();
  const payable = fee > 0 && !['cancelled', 'absent'].includes(appointment.appointment_status) && ['unpaid', 'pending'].includes(paymentStatus || '');
  const label = payable ? paymentStatus === 'pending' ? 'Resume payment' : 'Pay consultation fee' : paymentStatus === 'paid' ? 'View receipt' : 'Payment & receipt';
  return <Link className={`${payable ? 'btn-primary' : 'btn-secondary'} w-full text-sm`} to={`/dashboard/patient/payments?appointment_id=${appointment.id}`}>{payable ? <CreditCard className="h-4 w-4" /> : <Receipt className="h-4 w-4" />}{t(label)}</Link>;
}

export function AppointmentActions({ appointment, updated }: { appointment: Appointment; updated: (appointment?: Appointment) => void }) {
  const { t: uiText } = useLanguage();
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<Schedule[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  return <div className="space-y-3">
    <div className="flex flex-wrap gap-2">
      {['booked', 'confirmed'].includes(appointment.appointment_status) && <button type="button" className="btn-secondary text-sm" onClick={async () => {
        setMessage(''); setSessions([]); setLoadingSessions(true); setOpen(true);
        try { const response = await apiClient.get(`/schedules/doctor/${appointment.doctor_id}`); const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dhaka' }); setSessions(response.data.data.filter((session: Schedule) => session.id !== appointment.schedule_id && session.status === 'open' && session.schedule_date >= today)); }
        catch (error) { setMessage(errorMessage(error)); }
        finally { setLoadingSessions(false); }
      }}><CalendarClock className="h-4 w-4" />{t('Reschedule visit')}</button>}
      {appointment.consultation_mode === 'video' && <button type="button" className="btn-secondary text-sm" onClick={async () => {
        try { const response = await apiClient.get(`/appointments/${appointment.id}/video`); window.open(response.data.data.url, '_blank', 'noopener,noreferrer'); }
        catch (error) { setMessage(errorMessage(error)); }
      }}><Video className="h-4 w-4" /> <I18nText text={"Join video consultation"} /> </button>}
      <button type="button" className="btn-secondary text-sm" onClick={async () => {
        try { const response = await apiClient.get(`/appointments/${appointment.id}/fhir`); const url = URL.createObjectURL(new Blob([JSON.stringify(response.data.data, null, 2)], { type: 'application/fhir+json' })); const link = document.createElement('a'); link.href = url; link.download = `appointment-${appointment.id}.json`; link.click(); URL.revokeObjectURL(url); }
        catch (error) { setMessage(errorMessage(error)); }
      }}><Download className="h-4 w-4" /> <I18nText text={"Download appointment"} /> </button>
    </div>
    {message && !open && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{message}</p>}
    <Modal isOpen={open} onClose={() => { if (!busy) setOpen(false); }} title={uiText("Reschedule consultation")}>
      <form className="space-y-4" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setMessage('');
        try { const result = await apiClient.post(`/appointments/${appointment.id}/reschedule`, Object.fromEntries(new FormData(event.currentTarget))); setOpen(false); updated(result.data.data); }
        catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
      }}>
        <p className="text-sm text-slate-600"> <I18nText text={"Your current appointment stays booked until the new session is confirmed."} /> </p>
        {message && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{message}</p>}
        <label className="block text-sm font-medium"> <I18nText text={"New session"} /> <select name="schedule_id" aria-label={uiText("New session")} required disabled={loadingSessions || busy} className="input-field mt-2"><option value="">{loadingSessions ? 'Loading available sessions…' : 'Choose a session'}</option>{sessions.map(session => <option key={session.id} value={session.id}>{session.schedule_date} · {session.start_time.slice(0, 5)} · {session.chamber?.name}</option>)}</select></label>
        {!loadingSessions && !sessions.length && !message && <p className="text-sm text-slate-500"> <I18nText text={"No alternative sessions are available. You can keep this booking and check again later."} /> </p>}
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 border-t pt-4"><button type="button" disabled={busy} onClick={() => setOpen(false)} className="btn-secondary text-sm"> <I18nText text={"Keep current appointment"} /> </button><button disabled={busy || loadingSessions || !sessions.length} className="btn-primary text-sm">{busy ? 'Rescheduling…' : 'Confirm reschedule'}</button></div>
      </form>
    </Modal>
  </div>;
}
