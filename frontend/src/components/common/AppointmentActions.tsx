import { useLanguage } from '../../context/LanguageContext';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { Appointment, Schedule } from '../../types';
import { Modal } from './Modal';

export function AppointmentActions({ appointment, updated }: { appointment: Appointment; updated: () => void }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<Schedule[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  return <div className="space-y-2">
    <Link className="underline text-sm" to={`/dashboard/patient/tools?tab=billing&appointment_id=${appointment.id}`}>{t('Payment & receipt')}</Link>
    <button className="underline text-sm" onClick={async () => {
      try { const r = await apiClient.get(`/appointments/${appointment.id}/fhir`); const url = URL.createObjectURL(new Blob([JSON.stringify(r.data.data, null, 2)], { type: 'application/fhir+json' })); const link = document.createElement('a'); link.href = url; link.download = `appointment-${appointment.id}.json`; link.click(); URL.revokeObjectURL(url); }
      catch (error) { setMessage(errorMessage(error)); }
    }}>Export appointment (FHIR)</button>
    {['booked', 'confirmed'].includes(appointment.appointment_status) && <button className="btn-secondary text-xs" onClick={async () => {
      setOpen(true);
      try { const r = await apiClient.get(`/schedules/doctor/${appointment.doctor_id}`); setSessions(r.data.data.filter((s: Schedule) => s.id !== appointment.schedule_id && s.status === 'open')); }
      catch (e) { setMessage(errorMessage(e)); }
    }}>{t('Reschedule visit')}</button>}
    {(appointment as any).consultation_mode === 'video' && <button className="btn-secondary" onClick={async () => {
      try { const r = await apiClient.get(`/appointments/${appointment.id}/video`); window.open(r.data.data.url, '_blank', 'noopener,noreferrer'); }
      catch (e) { setMessage(errorMessage(e)); }
    }}>Join video consultation</button>}
    {message && <p role="status" className="text-sm">{message}</p>}
    <Modal isOpen={open} onClose={() => setOpen(false)} title="Reschedule consultation">
      <form className="space-y-4" onSubmit={async e => {
        e.preventDefault(); setBusy(true); setMessage('');
        try { await apiClient.post(`/appointments/${appointment.id}/reschedule`, Object.fromEntries(new FormData(e.currentTarget))); setOpen(false); updated(); }
        catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
      }}>
        <p>Your existing booking remains in place unless the new booking succeeds.</p>
        {message && <p role="alert">{message}</p>}
        <label className="block">New session<select name="schedule_id" aria-label="New session" required className="input-field">
          <option value="">Choose a session</option>{sessions.map(s => <option key={s.id} value={s.id}>{s.schedule_date} · {s.start_time.slice(0, 5)} · {s.chamber?.name}</option>)}
        </select></label>
        {!sessions.length && <p>No alternative open sessions are available.</p>}
        <button disabled={busy || !sessions.length} className="btn-primary">Confirm reschedule</button>
      </form>
    </Modal>
  </div>;
}
