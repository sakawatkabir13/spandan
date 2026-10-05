import { useLanguage } from '../../context/LanguageContext';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useAuth } from '../../context/AuthContext';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { Modal } from '../../components/common/Modal';
import { ScheduleEditor } from '../../components/common/ManagementEditors';
import { Schedule } from '../../types';

type Row = Record<string, any>;
const Input = ({ name, type = 'text', label, required = true }: { name: string; type?: string; label?: string; required?: boolean }) =>
  <label className="block text-sm">{label || name.replaceAll('_', ' ')}<input aria-label={label || name.replaceAll('_', ' ')} name={name} type={type} required={required} className="input-field" /></label>;

export function ToolsPage() {
  const { t } = useLanguage();
  const { user, logout } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') || 'notifications';
  const [rows, setRows] = useState<Row[]>([]);
  const [analytics, setAnalytics] = useState<Row | null>(null);
  const [system, setSystem] = useState<Row | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState('');
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [month, setMonth] = useState(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dhaka' }).slice(0, 7));
  const [receipt, setReceipt] = useState<Row | null>(null);
  const [payment, setPayment] = useState<Row | null>(null);
  const patient = user?.role === 'patient';
  const admin = user?.role === 'administrator';
  const tabs = ['notifications', 'security', 'privacy', ...(patient ? ['family', 'waitlist', 'billing'] : ['calendar', 'analytics', 'billing']), ...(admin ? ['directory'] : [])];
  const load = async () => {
    try {
      if (tab === 'analytics') { setAnalytics((await apiClient.get('/analytics')).data.data); if (admin) setSystem((await apiClient.get('/system/status')).data.data); return; }
      const endpoint = { notifications: '/notifications', family: '/dependents', waitlist: '/waitlist', privacy: '/privacy/requests', calendar: '/schedules/me', directory: admin ? '/directory/admin/doctors' : undefined }[tab];
      setRows(endpoint ? (await apiClient.get(endpoint)).data.data : []);
      if (tab === 'billing' && (params.get('appointment_id') || payment?.appointment_id)) {
        const id = params.get('appointment_id') || payment?.appointment_id;
        setPayment({ ...(await apiClient.get(`/payments/appointment/${id}`)).data.data, appointment_id: id });
      }
    } catch (error) { setMessage(errorMessage(error)); }
  };
  useEffect(() => { setMessage(''); setRows([]); void load(); }, [tab, params.get('appointment_id')]);
  const act = async (path: string, data: any = {}, method = 'post') => {
    setBusy(true); setMessage('');
    if (tab === 'billing' && method !== 'get') setReceipt(null);
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
  return <DashboardLayout><div className="space-y-6">
    <h1 className="text-2xl font-bold">{t('Account & Chamber Tools')}</h1>
    <nav className="flex flex-wrap gap-2" aria-label="Tools">{tabs.map(name => <button key={name} onClick={() => setParams({ tab: name })} className={tab === name ? 'btn-primary capitalize' : 'btn-secondary capitalize'}>{t(name)}</button>)}</nav>
    {message && <p role="status" className="rounded-xl bg-spandan-50 p-4">{message}</p>}
    {tab === 'directory' && admin && <section className="glass-card p-6 space-y-4"><h2 className="text-xl font-bold">{t('Public hospital directory')}</h2><p>Doctor information is sourced from hospital websites. Hide outdated listings until their sources can be reviewed. Imports preserve your visibility decisions.</p>{!rows.length && <p>No imported listings.</p>}{rows.map(row => <article key={row.id} className="border-t py-4 flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">{row.full_name}</h3><p className="text-sm">{row.institution} · {row.division}</p><a className="text-sm underline" href={row.source_url} target="_blank" rel="noopener noreferrer">Official source · reviewed {row.source_checked_on}</a></div><button disabled={busy} className="btn-secondary" onClick={() => void act(`/directory/admin/doctors/${row.id}`, { is_active: !row.is_active }, 'patch')}>{row.is_active ? 'Hide listing' : 'Publish listing'}</button></article>)}</section>}
    {tab === 'notifications' && <section className="glass-card p-6 space-y-4">{!rows.length && <p>No notifications yet.</p>}{rows.map(row => <article key={row.id} className="border-b py-3">
      <h2 className="font-bold">{row.subject}</h2><p>{row.message}</p><p className="text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</p>
      {!row.read_at && <button className="btn-secondary mt-2" disabled={busy} onClick={() => void act(`/notifications/${row.id}/read`)}>Mark read</button>}
    </article>)}</section>}
    {tab === 'security' && <section className="glass-card p-6 space-y-5">
      <h2 className="text-xl font-bold">Contact verification & authenticator</h2>
      <div className="flex flex-wrap gap-3"><button className="btn-secondary" disabled={busy} onClick={() => void act('/auth/verify/email/request')}>Verify email</button><button className="btn-secondary" disabled={busy} onClick={() => void act('/auth/verify/phone/request')}>Send phone code</button><Link className="btn-secondary" to={`/account-action?purpose=phone&email=${encodeURIComponent(user?.email || '')}`}>Enter phone code</Link></div>
      <p>Authenticator setup requires your current password. Enabling or disabling it signs out existing sessions.</p>
      <form className="space-y-3 max-w-md" onSubmit={async e => { e.preventDefault(); const data = Object.fromEntries(new FormData(e.currentTarget)); const r = await act('/auth/mfa/setup', data); if (r) setSecret(r.secret); }}>
        <Input name="password" type="password" /><button disabled={busy} className="btn-secondary">Set up authenticator</button>
      </form>
      {secret && <p className="break-all rounded-xl bg-slate-100 p-4">Save this secret in your authenticator: <code>{secret}</code>. Then enter its six-digit code below.</p>}
      <form className="space-y-3 max-w-md" onSubmit={async e => {
        e.preventDefault(); setBusy(true);
        const fields = Object.fromEntries(new FormData(e.currentTarget));
        try { await apiClient.post(`/auth/mfa/${fields.action}`, { password: fields.password, code: fields.code }); await logout(false); window.location.assign('/login'); }
        catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
      }}><Input name="password" type="password" /><Input name="code" /><label className="block">Action<select name="action" className="input-field"><option value="enable">Enable</option><option value="disable">Disable</option></select></label><button disabled={busy} className="btn-primary">Confirm authenticator</button></form>
    </section>}
    {tab === 'family' && <section className="glass-card p-6 space-y-4">
      <h2 className="text-xl font-bold">{t('Family members')}</h2><p>You can choose a family member when booking an appointment.</p>
      <form onSubmit={submit('/dependents')} className="grid sm:grid-cols-2 gap-3"><Input name="full_name" /><Input name="relationship_name" /><Input name="date_of_birth" type="date" required={false} /><button disabled={busy} className="btn-primary">{t('Add family member')}</button></form>
      {rows.map(row => <div key={row.id} className="flex justify-between border-t py-3"><p>{row.full_name} · {row.relationship_name}</p><button disabled={busy} className="btn-secondary" onClick={() => void act(`/dependents/${row.id}`, {}, 'delete')}>Archive</button></div>)}
    </section>}
    {tab === 'waitlist' && <section className="glass-card p-6 space-y-4"><p>Join a full session's cancellation waitlist from the doctor's profile. A notification signals availability; it does not reserve a place.</p>{rows.map(row => <div key={row.id} className="flex flex-wrap gap-3 border-t py-3"><p>Waiting since {new Date(row.created_at).toLocaleDateString()}</p><button disabled={busy} className="btn-secondary" onClick={() => void act(`/waitlist/${row.id}`, {}, 'delete')}>Leave waitlist</button></div>)}</section>}
    {tab === 'calendar' && <section className="glass-card p-6 space-y-4">
      <h2 className="text-xl font-bold">Availability calendar</h2><label>Month<input type="month" value={month} onChange={e => setMonth(e.target.value)} className="input-field max-w-xs" /></label>
      {!rows.length && <p role="alert">No upcoming sessions. Publish availability from Chamber & Schedules to accept bookings.</p>}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{rows.filter(row => row.schedule_date.startsWith(month)).map(row => <article key={row.id} className="border rounded-xl p-4 space-y-2">
        <h3 className="font-bold">{row.schedule_date}</h3><p>{row.chamber?.name}</p><p>{row.start_time.slice(0, 5)}–{row.end_time.slice(0, 5)} · {row.status}</p>
        <Link className="underline" to={`/dashboard/${admin ? 'admin' : user?.role === 'doctor' ? 'doctor' : 'assistant'}/queue?schedule_id=${row.id}`}>Open queue</Link>
        <button className="btn-secondary" onClick={() => setEditing(row as Schedule)}>Edit session</button>
      </article>)}</div>
      {user?.role === 'doctor' && <><h3 className="font-bold">Holiday or closure</h3><form className="grid sm:grid-cols-3 gap-3" onSubmit={submit('/availability/exceptions')}><Input name="exception_date" type="date" /><Input name="reason" /><button className="btn-secondary" disabled={busy}>Add closure</button></form><Closures key={message} /></>}
    </section>}
    {tab === 'analytics' && analytics && <section className="glass-card p-6 space-y-5">
      {system && <div className="rounded-xl border p-4"><h2 className="font-bold">Service monitoring</h2>{Object.entries(system).map(([name, value]) => <p key={name}>{name.replaceAll('_', ' ')}: {typeof value === 'boolean' ? (value ? 'Enabled' : 'Disabled') : String(value)}</p>)}</div>}
      <h2 className="text-xl font-bold">Last {analytics.days} days</h2>
      <div className="grid sm:grid-cols-3 gap-4">{[['Bookings', analytics.total_bookings], ['Upcoming sessions', analytics.upcoming_sessions], ['Attendance', `${analytics.attendance_rate}%`]].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-spandan-50 p-5"><p>{label}</p><strong className="text-3xl">{value}</strong></div>)}</div>
      {Object.entries(analytics.status_counts).map(([status, count]) => <div key={status}><div className="flex justify-between"><span>{status.replaceAll('_', ' ')}</span><span>{String(count)}</span></div><div className="h-3 rounded bg-slate-100"><div className="h-3 rounded bg-spandan-500" style={{ width: `${100 * Number(count) / Math.max(1, analytics.total_bookings)}%` }} /></div></div>)}
      <p>Average consultation: {analytics.average_consultation_minutes ?? 'No completed visits'} minutes.</p>
    </section>}
    {tab === 'privacy' && <section className="glass-card p-6 space-y-4"><h2 className="text-xl font-bold">Personal data requests</h2>
      <button disabled={busy} className="btn-secondary" onClick={async () => { const data = await act('/privacy/export', {}, 'get'); if (data) { const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = 'spandan-personal-data.json'; a.click(); URL.revokeObjectURL(url); } }}>Download my data</button>
      {!admin && <div className="flex gap-3"><button disabled={busy} className="btn-secondary" onClick={() => void act('/privacy/requests', { kind: 'access' })}>Request access review</button><button disabled={busy} className="btn-danger" onClick={() => { if (confirm('Request account anonymization? Active appointments must be resolved first.')) void act('/privacy/requests', { kind: 'deletion' }); }}>Request deletion review</button></div>}
      {rows.map(row => <article key={row.id} className="border-t py-3"><p>{row.kind} · {row.status} · {new Date(row.created_at).toLocaleDateString()}</p>{admin && row.status === 'pending' && <button className="btn-secondary mt-2" onClick={() => { if (confirm('Resolve this privacy request? Deletion requests anonymize the account.')) void act(`/privacy/requests/${row.id}/resolve`); }}>Resolve request</button>}</article>)}
    </section>}
    {tab === 'billing' && <section className="glass-card p-6 space-y-4"><h2 className="text-xl font-bold">Payments & receipts</h2><p>Use the appointment ID from your booking. Stripe checkout runs in test mode only. You can also test payment outcomes without entering card details. No real money is charged.</p>
      <form className="flex flex-wrap gap-3" onSubmit={async e => { e.preventDefault(); const fields = Object.fromEntries(new FormData(e.currentTarget)); const r = await act(`/payments/appointment/${fields.appointment_id}`, {}, 'get'); if (r) setPayment({ ...r, appointment_id: fields.appointment_id }); }}><Input name="appointment_id" label="Appointment ID" /><button disabled={busy} className="btn-secondary">Find payment</button></form>
      {payment && <div className="space-y-3"><p>Fee: {payment.fee} {payment.currency.toUpperCase()} · {payment.payment?.status || 'Unpaid'}</p>
        {patient && payment.online_enabled && (!payment.payment || payment.payment.status === 'pending') && <button className="btn-primary" onClick={async () => { const r = await act(`/payments/appointment/${payment.appointment_id}/checkout`); if (r?.url) window.location.assign(r.url); }} disabled={busy}>Open Stripe test checkout</button>}
        {patient && payment.payment?.status === 'pending' && payment.payment.provider === 'stripe' && <button disabled={busy} className="btn-secondary" onClick={() => void act(`/payments/${payment.payment.id}/cancel-checkout`)}>Cancel pending test checkout</button>}
        {patient && payment.demo_enabled && !payment.payment && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-3"><p>Payment simulator: no card details, no money charged, no Stripe transaction.</p><div className="flex flex-wrap gap-3"><button disabled={busy} className="btn-primary" onClick={() => void act(`/payments/appointment/${payment.appointment_id}/demo`, { outcome: 'success' })}>Simulate successful payment</button><button disabled={busy} className="btn-secondary" onClick={() => void act(`/payments/appointment/${payment.appointment_id}/demo`, { outcome: 'declined' })}>Simulate declined payment</button></div></div>}
        {!patient && !payment.payment && <button className="btn-secondary" onClick={() => { if (confirm('Confirm that the consultation fee was received in cash?')) void act(`/payments/appointment/${payment.appointment_id}/cash`, { method: 'cash' }); }}>Record cash received</button>}
        {payment.payment && ['paid', 'refunded', 'refund_pending'].includes(payment.payment.status) && <button className="btn-secondary" onClick={async () => { const r = await act(`/payments/${payment.payment.id}/receipt`, {}, 'get'); if (r) setReceipt(r); }}>View receipt</button>}
        {['doctor', 'administrator'].includes(user?.role || '') && payment.payment?.status === 'paid' && <button className="btn-danger" onClick={() => { if (confirm('Refund this cancelled appointment? Return any cash payment to the patient.')) void act(`/payments/${payment.payment.id}/refund`); }}>Refund cancelled visit</button>}
      </div>}
      {receipt && <article className="border rounded-xl p-5 space-y-2"><h3 className="text-xl font-bold">{receipt.operator} receipt</h3>{receipt.is_test && <p className="font-semibold text-amber-800">TEST RECEIPT — no real payment. Provider: {receipt.provider === 'demo' ? 'Payment simulator' : receipt.provider}</p>}<p>{receipt.contact}</p><p>Receipt: {receipt.receipt_number}</p><p>Serial {receipt.serial_number} · {receipt.session_date}</p><p>{receipt.amount} {receipt.currency.toUpperCase()} · {receipt.status}</p><button className="btn-secondary print:hidden" onClick={() => window.print()}>Print receipt</button></article>}
    </section>}
    <Modal isOpen={!!editing} onClose={() => setEditing(null)} title="Edit consultation session">{editing && <ScheduleEditor schedule={editing} saved={() => { setEditing(null); void load(); }} />}</Modal>
  </div></DashboardLayout>;
}

function Closures() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { apiClient.get('/availability/exceptions').then(r => setRows(r.data.data)).catch(e => setError(errorMessage(e))); }, []);
  return <div>{error && <p role="alert">{error}</p>}{rows.map(row => <div key={row.id} className="flex flex-wrap justify-between border-t p-3"><p>{row.exception_date} · {row.reason}</p><button className="btn-secondary" onClick={async () => { try { await apiClient.delete(`/availability/exceptions/${row.id}`); setRows(all => all.filter(r => r.id !== row.id)); } catch (e) { setError(errorMessage(e)); } }}>Remove closure</button></div>)}</div>;
}
