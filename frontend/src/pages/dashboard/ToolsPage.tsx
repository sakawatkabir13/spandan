import { FamilyMembersPanel } from '../../components/common/FamilyMembersPanel';
import { I18nText } from '../../context/LanguageContext';
import { PaymentsPanel } from '../../components/common/PaymentsPanel';
import { useLanguage } from '../../context/LanguageContext';
import { useEffect, useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useAuth } from '../../context/AuthContext';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { Modal } from '../../components/common/Modal';
import { ScheduleEditor } from '../../components/common/ManagementEditors';
import { Schedule } from '../../types';
import { AccountDevices } from '../../components/common/AccountDevices';
import { WaitlistPanel } from '../../components/common/WaitlistPanel';
import { ReviewVisits } from '../../components/common/ReviewVisits';

type Row = Record<string, any>;
const Input = ({ name, type = 'text', label, required = true }: { name: string; type?: string; label?: string; required?: boolean }) =>
  <label className="block text-sm">{label || name.replaceAll('_', ' ')}<input aria-label={label || name.replaceAll('_', ' ')} name={name} type={type} required={required} className="input-field" /></label>;

export function ToolsPage() {
  const { t: uiText } = useLanguage();
  const { t } = useLanguage();
  const { user, logout } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') || 'notifications';
  const [rows, setRows] = useState<Row[]>([]);
  const [analytics, setAnalytics] = useState<Row | null>(null);
  const [system, setSystem] = useState<Row | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [secret, setSecret] = useState('');
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [month, setMonth] = useState(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dhaka' }).slice(0, 7));
  const patient = user?.role === 'patient';
  const admin = user?.role === 'administrator';
  const tabs = ['notifications', 'security', 'privacy', ...(patient ? ['family', 'waitlist'] : ['calendar', 'review', 'analytics', 'billing']), ...(admin ? ['directory'] : [])];
  const load = async () => {
    setLoading(true);
    try {
      if (tab === 'analytics') { setAnalytics((await apiClient.get('/analytics')).data.data); if (admin) setSystem((await apiClient.get('/system/status')).data.data); return; }
      const endpoint = { notifications: '/notifications', family: '/dependents', waitlist: '/waitlist', privacy: '/privacy/requests', calendar: '/schedules/me', directory: admin ? '/directory/admin/doctors' : undefined }[tab];
      setRows(endpoint ? (await apiClient.get(endpoint)).data.data : []);

    } catch (error) { setMessage(errorMessage(error)); }
    finally { setLoading(false); }
  };
  useEffect(() => { setMessage(''); setRows([]); void load(); }, [tab, params.get('appointment_id')]);
  const act = async (path: string, data: any = {}, method = 'post') => {
    setBusy(true); setMessage('');
    try { const r = await apiClient.request({ url: path, method, data }); setMessage(r.data.message); await load(); return r.data.data; }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(false); }
  };
  const submit = (path: string) => async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    const result = await act(path, data);
    if (result) form.reset();
  };
  if (patient && tab === 'billing') return <Navigate to={`/dashboard/patient/payments?${params.toString()}`} replace />;
  return <DashboardLayout><div className="space-y-6">
    <header><h1 className="text-2xl sm:text-3xl font-bold">{patient ? 'Account settings' : t('Account & Chamber Tools')}</h1><p className="mt-2 text-sm text-slate-600">{patient ? 'Manage notifications, security, family members, and privacy.' : 'Manage account preferences and chamber operations.'}</p></header>
    <nav className="segmented-control" aria-label={uiText("Tools")}>{tabs.map(name => <button key={name} onClick={() => setParams({ tab: name })} aria-pressed={tab === name} className="capitalize shrink-0">{t(name)}</button>)}</nav>
    {loading && <p role="status" className="text-sm text-slate-500"> <I18nText text={"Loading account information…"} /> </p>}
    {message && <p role="status" className="rounded-xl bg-spandan-50 p-4">{message}</p>}
    {tab === 'directory' && admin && <section className="glass-card p-6 space-y-4"><h2 className="text-xl font-bold">{t('Public hospital directory')}</h2><p> <I18nText text={"Doctor information is sourced from hospital websites. Hide outdated listings until their sources can be reviewed. Imports preserve your visibility decisions."} /> </p>{!rows.length && <p> <I18nText text={"No imported listings."} /> </p>}{rows.map(row => <article key={row.id} className="border-t py-4 flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">{row.full_name}</h3><p className="text-sm">{row.institution} · {row.division}</p><a className="text-sm underline" href={row.source_url} target="_blank" rel="noopener noreferrer"> <I18nText text={"Official source · reviewed"} /> {row.source_checked_on}</a></div><button disabled={busy} className="btn-secondary" onClick={() => void act(`/directory/admin/doctors/${row.id}`, { is_active: !row.is_active }, 'patch')}>{row.is_active ? 'Hide listing' : 'Publish listing'}</button></article>)}</section>}
    {tab === 'notifications' && <section className="glass-card p-6 space-y-4">{!loading && !rows.length && <p> <I18nText text={"No notifications yet. Your appointment updates will appear here."} /> </p>}{rows.map(row => <article key={row.id} className="border-b py-3">
      <h2 className="font-bold">{row.subject}</h2><p>{row.message}</p><p className="text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</p>
      {patient && /\/dashboard\/patient\/appointments\/[0-9a-f-]{36}/.test(row.message) && <Link className="btn-primary mt-3 mr-2 text-sm" to={row.message.match(/\/dashboard\/patient\/appointments\/[0-9a-f-]{36}/)![0]}> <I18nText text={"Open appointment"} /> </Link>}
      {patient && row.message.includes('/dashboard/patient/tools?tab=waitlist') && <Link className="btn-primary mt-3 mr-2 text-sm" to="/dashboard/patient/tools?tab=waitlist"> <I18nText text={"View waitlist offer"} /> </Link>}
      {!row.read_at && <button className="btn-secondary mt-2" disabled={busy} onClick={() => void act(`/notifications/${row.id}/read`)}> <I18nText text={"Mark read"} /> </button>}
    </article>)}</section>}
    {tab === 'security' && <section className="glass-card p-6 space-y-5">
      <h2 className="text-xl font-bold"> <I18nText text={"Contact verification & authenticator"} /> </h2>
      <div className="flex flex-wrap gap-3"><button className="btn-secondary" disabled={busy} onClick={() => void act('/auth/verify/email/request')}> <I18nText text={"Verify email"} /> </button><button className="btn-secondary" disabled={busy} onClick={() => void act('/auth/verify/phone/request')}> <I18nText text={"Send phone code"} /> </button><Link className="btn-secondary" to={`/account-action?purpose=phone&email=${encodeURIComponent(user?.email || '')}`}> <I18nText text={"Enter phone code"} /> </Link></div>
      <p> <I18nText text={"Authenticator setup requires your current password. Enabling or disabling it signs out existing sessions."} /> </p>
      <form className="space-y-3 max-w-md" onSubmit={async e => { e.preventDefault(); const data = Object.fromEntries(new FormData(e.currentTarget)); const r = await act('/auth/mfa/setup', data); if (r) setSecret(r.secret); }}>
        <Input name="password" type="password" /><button disabled={busy} className="btn-secondary"> <I18nText text={"Set up authenticator"} /> </button>
      </form>
      {secret && <p className="break-all rounded-xl bg-slate-100 p-4"> <I18nText text={"Save this secret in your authenticator:"} /> <code>{secret}</code> <I18nText text={". Then enter its six-digit code below."} /> </p>}
      <form className="space-y-3 max-w-md" onSubmit={async e => {
        e.preventDefault(); setBusy(true);
        const fields = Object.fromEntries(new FormData(e.currentTarget));
        try { await apiClient.post(`/auth/mfa/${fields.action}`, { password: fields.password, code: fields.code }); await logout(false); window.location.assign('/login'); }
        catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
      }}><Input name="password" type="password" /><Input name="code" /><label className="block"> <I18nText text={"Action"} /> <select name="action" className="input-field"><option value="enable"> <I18nText text={"Enable"} /> </option><option value="disable"> <I18nText text={"Disable"} /> </option></select></label><button disabled={busy} className="btn-primary"> <I18nText text={"Confirm authenticator"} /> </button></form>
    </section>}
    {tab === 'security' && <AccountDevices />}
    {tab === 'family' && <FamilyMembersPanel />}
    {tab === 'waitlist' && <WaitlistPanel />}
    {tab === 'review' && !patient && <ReviewVisits />}
    {tab === 'calendar' && <section className="glass-card p-6 space-y-4">
      <h2 className="text-xl font-bold"> <I18nText text={"Availability calendar"} /> </h2><label> <I18nText text={"Month"} /> <input type="month" value={month} onChange={e => setMonth(e.target.value)} className="input-field max-w-xs" /></label>
      {!rows.length && <p role="alert"> <I18nText text={"No upcoming sessions. Publish availability from Chamber & Schedules to accept bookings."} /> </p>}
      <div className="grid sm:grid-cols-2 2xl:grid-cols-3 gap-3">{rows.filter(row => row.schedule_date.startsWith(month)).map(row => <article key={row.id} className="border rounded-xl p-4 space-y-2">
        <h3 className="font-bold">{row.schedule_date}</h3><p>{row.chamber?.name}</p><p>{row.start_time.slice(0, 5)}–{row.end_time.slice(0, 5)} · {row.status}</p>
        <Link className="underline" to={`/dashboard/${admin ? 'admin' : user?.role === 'doctor' ? 'doctor' : 'assistant'}/queue?schedule_id=${row.id}`}> <I18nText text={"Open queue"} /> </Link>
        <button className="btn-secondary" onClick={() => setEditing(row as Schedule)}> <I18nText text={"Edit session"} /> </button>
        {['open', 'full'].includes(row.status) && <button className="btn-secondary" disabled={busy} onClick={() => { if (confirm('Confirm that the doctor plans to attend this session?')) void act(`/schedules/${row.id}/confirm`); }}> <I18nText text={"Confirm availability"} /> </button>}
        <p className="text-xs text-slate-500">{row.confirmed_at ? `Staff confirmed: ${new Date(row.confirmed_at).toLocaleString('en-GB')}` : 'Attendance confirmation pending'}</p>
      </article>)}</div>
      {user?.role === 'doctor' && <><h3 className="font-bold"> <I18nText text={"Holiday or closure"} /> </h3><form className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3 items-end" onSubmit={submit('/availability/exceptions')}><Input name="exception_date" type="date" /><Input name="reason" /><button className="btn-secondary" disabled={busy}> <I18nText text={"Add closure"} /> </button></form><Closures key={message} /></>}
    </section>}
    {tab === 'analytics' && analytics && <section className="glass-card p-6 space-y-5">
      {system && <div className="rounded-xl border p-4"><h2 className="font-bold"> <I18nText text={"Service monitoring"} /> </h2>{Object.entries(system).map(([name, value]) => <p key={name}>{name.replaceAll('_', ' ')}: {typeof value === 'boolean' ? (value ? 'Enabled' : 'Disabled') : String(value)}</p>)}</div>}
      <h2 className="text-xl font-bold"> <I18nText text={"Last"} /> {analytics.days}  <I18nText text={"days"} /> </h2>
      <div className="grid sm:grid-cols-3 gap-4">{[['Bookings', analytics.total_bookings], ['Upcoming sessions', analytics.upcoming_sessions], ['Attendance', `${analytics.attendance_rate}%`]].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-spandan-50 p-5"><p>{label}</p><strong className="text-3xl">{value}</strong></div>)}</div>
      {Object.entries(analytics.status_counts).map(([status, count]) => <div key={status}><div className="flex justify-between"><span>{status.replaceAll('_', ' ')}</span><span>{String(count)}</span></div><div className="h-3 rounded bg-slate-100"><div className="h-3 rounded bg-spandan-500" style={{ width: `${100 * Number(count) / Math.max(1, analytics.total_bookings)}%` }} /></div></div>)}
      <p> <I18nText text={"Average consultation:"} /> {analytics.average_consultation_minutes ?? 'No completed visits'}  <I18nText text={"minutes."} /> </p>
      {analytics.care && <div className="border-t border-slate-100 pt-5"><h3 className="section-heading mb-4"> <I18nText text={"Patient journey & reliability"} /> </h3><dl className="grid gap-3 sm:grid-cols-2">{[['Booking completion', analytics.care.booking_completion_percent === null ? 'No tracked starts yet' : `${analytics.care.booking_completion_percent}% (${analytics.care.booking_completions}/${analytics.care.booking_starts})`], ['Recorded payment failures', analytics.care.payment_failures], ['Payments awaiting completion', analytics.care.pending_payments], ['No-show rate', analytics.care.no_show_percent === null ? 'No resolved visits yet' : `${analytics.care.no_show_percent}%`], ['Mean booking estimate error', analytics.care.booking_estimate_mean_error_minutes === null ? 'No timing samples yet' : `${analytics.care.booking_estimate_mean_error_minutes} minutes (${analytics.care.booking_estimate_sample_count} visits)`], ['Charts reviewed before consultation', `${analytics.care.charts_reviewed_before_consultation}/${analytics.care.consultations_started}`]].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-slate-50 p-4"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-sm font-semibold">{String(value)}</dd></div>)}</dl><p className="mt-3 text-xs text-slate-500"> <I18nText text={"Booking completion covers tracked booking starts completed within 30 minutes. Timing error compares the original booking estimate with the actual consultation start. Payment failures count verified provider failure events."} /> </p></div>}
    </section>}
    {tab === 'privacy' && <section className="glass-card p-6 space-y-4"><h2 className="text-xl font-bold"> <I18nText text={"Personal data requests"} /> </h2>
      <button disabled={busy} className="btn-secondary" onClick={async () => { const data = await act('/privacy/export', {}, 'get'); if (data) { const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = 'spandan-personal-data.json'; a.click(); URL.revokeObjectURL(url); } }}> <I18nText text={"Download my data"} /> </button>
      {!admin && <div className="flex flex-wrap gap-3"><button disabled={busy} className="btn-secondary" onClick={() => void act('/privacy/requests', { kind: 'access' })}> <I18nText text={"Request access review"} /> </button><button disabled={busy} className="btn-danger" onClick={() => { if (confirm('Request account anonymization? Active appointments must be resolved first.')) void act('/privacy/requests', { kind: 'deletion' }); }}> <I18nText text={"Request deletion review"} /> </button></div>}
      {rows.map(row => <article key={row.id} className="border-t py-3"><p>{row.kind} · {row.status} · {new Date(row.created_at).toLocaleDateString()}</p>{admin && row.status === 'pending' && <button className="btn-secondary mt-2" onClick={() => { if (confirm('Resolve this privacy request? Deletion requests anonymize the account.')) void act(`/privacy/requests/${row.id}/resolve`); }}> <I18nText text={"Resolve request"} /> </button>}</article>)}
    </section>}
    {tab === 'billing' && <PaymentsPanel />}
    <Modal isOpen={!!editing} onClose={() => setEditing(null)} title={uiText("Edit consultation session")}>{editing && <ScheduleEditor schedule={editing} saved={() => { setEditing(null); void load(); }} />}</Modal>
  </div></DashboardLayout>;
}

function Closures() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { apiClient.get('/availability/exceptions').then(r => setRows(r.data.data)).catch(e => setError(errorMessage(e))); }, []);
  return <div>{error && <p role="alert">{error}</p>}{rows.map(row => <div key={row.id} className="flex flex-wrap justify-between border-t p-3"><p>{row.exception_date} · {row.reason}</p><button className="btn-secondary" onClick={async () => { try { await apiClient.delete(`/availability/exceptions/${row.id}`); setRows(all => all.filter(r => r.id !== row.id)); } catch (e) { setError(errorMessage(e)); } }}> <I18nText text={"Remove closure"} /> </button></div>)}</div>;
}
