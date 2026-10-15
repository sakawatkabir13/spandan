import { I18nText } from '../../context/LanguageContext';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useAuth } from '../../context/AuthContext';
import { Appointment } from '../../types';

export function ReviewVisits() {
  const { user } = useAuth();
  const [rows, setRows] = useState<{ appointment: Appointment; reason: string }[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const role = user?.role === 'administrator' ? 'admin' : user?.role;
  const load = async () => { try { setRows((await apiClient.get('/workspace/review')).data.data); } catch (e) { setError(errorMessage(e)); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  return <section className="glass-card space-y-4 p-5 sm:p-6"><h2 className="section-heading"> <I18nText text={"Visits needing review"} /> </h2><p className="text-sm text-slate-500"> <I18nText text={"Unresolved sessions from the last 14 days, missed visits, and consultations left open for over an hour. Review before changing their status."} /> </p>{error && <p role="alert" className="text-red-700">{error}</p>}{loading && <p role="status"> <I18nText text={"Loading review list…"} /> </p>}{!loading && !rows.length && <p className="empty-state text-sm text-slate-500"> <I18nText text={"No unresolved visits found."} /> </p>}{rows.map(({ appointment: app, reason }) => <article key={app.id} className="space-y-3 border-t border-slate-100 py-4"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold">{app.attendee_name}  <I18nText text={"· Serial #"} /> {app.serial_number}</h3><p className="mt-1 text-sm text-slate-500">{app.chamber?.name} · {app.schedule?.schedule_date}</p></div><span className="text-sm text-amber-800">{reason}</span></div><div className="flex flex-wrap gap-3"><Link className="btn-secondary text-sm" to={`/dashboard/${role}/queue?schedule_id=${app.schedule_id}`}> <I18nText text={"Review queue"} /> </Link>{app.appointment_status === 'in_consultation' && <button className="btn-secondary text-sm" disabled={busy} onClick={async () => { if (!confirm('Confirm this consultation has finished?')) return; setBusy(true); try { await apiClient.patch(`/appointments/${app.id}/status`, { appointment_status: 'completed' }); await load(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}> <I18nText text={"Mark consultation complete"} /> </button>}</div></article>)}</section>;
}
