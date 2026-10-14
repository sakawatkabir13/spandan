import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle2, CreditCard, FileText, RefreshCw, ShieldCheck } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useAuth } from '../../context/AuthContext';
import { Badge } from './Badge';

type BillingAppointment = { id: string; doctor_name: string; patient_name: string; chamber_name: string; session_date: string; start_time: string; serial_number: number; appointment_status: string; amount: number; currency: string; payment_status: string; payment_id: string | null };
type Payment = { id: string; status: string; provider: string; is_test: boolean; amount: number; paid_at: string | null };
type Invoice = { appointment: { id: string; doctor_name: string; patient_name: string; chamber_name: string; session_date: string; start_time: string; serial_number: number; status: string }; fee: number; currency: string; payment: Payment | null; online_enabled: boolean; can_pay: boolean; test_mode: boolean };
type Receipt = { receipt_number: string; is_test: boolean; provider: string; operator: string; contact: string; amount: number; currency: string; status: string; paid_at: string | null; patient_name: string; doctor_name: string; chamber_name: string; serial_number: number; session_date: string };
const money = (amount: number, currency: string) => new Intl.NumberFormat('en-BD', { style: 'currency', currency: currency.toUpperCase() }).format(Number(amount));
const date = (value: string) => new Date(value + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const labels: Record<string, string> = { unpaid: 'Unpaid', pending: 'Awaiting payment', paid: 'Paid', refunded: 'Refunded', refund_pending: 'Refund processing' };

export function PaymentsPanel() {
  const { user } = useAuth();
  const patient = user?.role === 'patient';
  const [params, setParams] = useSearchParams();
  const selected = params.get('appointment_id') || '';
  const checkoutResult = params.get('checkout');
  const [appointments, setAppointments] = useState<BillingAppointment[]>([]);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const request = useRef(0);
  const refreshList = useCallback(async () => {
    const data: BillingAppointment[] = (await apiClient.get('/payments/appointments')).data.data;
    setAppointments(data);
    return data;
  }, []);
  useEffect(() => { let active = true;
    void refreshList().then(rows => { if (active && !selected && rows.length) { const first = rows.find(row => ['unpaid', 'pending'].includes(row.payment_status) && !['cancelled', 'absent'].includes(row.appointment_status)) || rows[0]; setParams({ tab: 'billing', appointment_id: first.id }, { replace: true }); } }).catch(e => { if (active) setError(errorMessage(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refreshList]);
  const refreshInvoice = useCallback(async () => {
    if (!selected) return;
    const id = ++request.current;
    const data: Invoice = (await apiClient.get(`/payments/appointment/${selected}`)).data.data;
    if (id === request.current) setInvoice(data);
    return data;
  }, [selected]);
  useEffect(() => { setInvoice(null); setReceipt(null); setError(''); setMessage(''); void refreshInvoice().catch(e => setError(errorMessage(e))); return () => { request.current++; }; }, [refreshInvoice]);
  const paymentId = invoice?.payment?.id;
  const paymentStatus = invoice?.payment?.status;
  useEffect(() => {
    if (checkoutResult !== 'success' || !paymentId || paymentStatus !== 'pending') return;
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const reconcile = async (attempt: number) => {
      try { await apiClient.post(`/payments/${paymentId}/refresh`); if (!active) return; const data = await refreshInvoice(); if (!active) return; if (data?.payment?.status === 'pending' && attempt < 4) timer = setTimeout(() => void reconcile(attempt + 1), 2500); else await refreshList(); }
      catch (e) { if (active) setError(errorMessage(e)); }
    };
    void reconcile(0);
    return () => { active = false; clearTimeout(timer); };
  }, [checkoutResult, paymentId, paymentStatus, refreshInvoice, refreshList]);
  const act = async (action: () => Promise<void>) => { setBusy(true); setError(''); setMessage(''); try { await action(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } };
  const status = invoice?.payment?.status || 'unpaid';
  return <section className="glass-card p-5 sm:p-7 space-y-6" aria-labelledby="payments-heading">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="payments-heading" className="text-2xl font-bold">Payments & receipts</h2><p className="text-sm text-slate-600 mt-1">Manage consultation fees, payment status, and receipts in one place.</p></div><CreditCard className="h-8 w-8 text-spandan-600" /></div>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error}<button className="ml-3 underline" disabled={busy} onClick={() => void act(async () => { await refreshList(); await refreshInvoice(); })}>Try again</button></p>}
    {message && <p role="status" className="rounded-xl bg-spandan-50 p-4 text-spandan-800">{message}</p>}
    {loading && <p role="status">Loading your appointments…</p>}
    {!loading && !appointments.length && !selected && <div className="rounded-2xl border border-dashed p-6 text-center space-y-3"><p>No appointments to bill yet.</p>{patient && <Link to="/doctors" className="btn-primary">Find a doctor</Link>}</div>}
    {(appointments.length > 0 || selected) && <label className="block text-sm font-medium">Choose appointment<select aria-label="Choose appointment" className="input-field mt-2" value={selected} disabled={busy} onChange={e => setParams({ tab: 'billing', appointment_id: e.target.value })}>
      <option value="" disabled>Select an appointment</option>{selected && !appointments.some(a => a.id === selected) && <option value={selected}>{invoice ? `${invoice.appointment.doctor_name} · ${date(invoice.appointment.session_date)}` : 'Selected appointment'}</option>}
      {appointments.map(a => <option key={a.id} value={a.id}>{date(a.session_date)} · {patient ? a.doctor_name : a.patient_name} · Serial {a.serial_number} · {labels[a.payment_status] || a.payment_status}</option>)}
    </select></label>}
    {selected && !invoice && !error && <p role="status">Loading consultation payment…</p>}
    {invoice && <>
      <div className="rounded-2xl border border-slate-200 p-5 space-y-4"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="text-lg font-semibold">{invoice.appointment.doctor_name}</h3><p className="text-sm text-slate-500">{invoice.appointment.chamber_name}</p></div><Badge variant={status === 'paid' ? 'success' : status === 'pending' || status === 'refund_pending' ? 'warning' : 'neutral'}>{labels[status] || status}</Badge></div>
        <dl className="grid sm:grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-500">Patient</dt><dd>{invoice.appointment.patient_name}</dd></div><div><dt className="text-slate-500">Consultation</dt><dd>{date(invoice.appointment.session_date)} · {invoice.appointment.start_time.slice(0, 5)} · Serial {invoice.appointment.serial_number}</dd></div></dl>
        <div className="border-t pt-4 flex flex-wrap justify-between gap-2"><p className="text-slate-600">Consultation fee</p><strong className="text-2xl">{money(invoice.fee, invoice.currency)}</strong></div>
      </div>
      {status === 'paid' && <p role="status" className="rounded-xl bg-spandan-50 p-4 text-spandan-900 flex gap-2"><CheckCircle2 className="h-5 w-5 shrink-0" />Payment confirmed. Your receipt is ready below.</p>}
      {checkoutResult === 'success' && status === 'pending' && <p role="status" className="rounded-xl bg-blue-50 p-4 text-blue-900">Confirming your payment with Stripe. This page will update automatically. Please do not pay again while confirmation is in progress.</p>}
      {checkoutResult === 'cancelled' && !['paid', 'refunded', 'refund_pending'].includes(status) && <p role="status" className="rounded-xl bg-slate-50 p-4">Checkout was closed. Your appointment is still booked. You can resume payment or pay at the chamber.</p>}
      {['cancelled', 'absent'].includes(invoice.appointment.status) && status === 'unpaid' && <p className="text-sm text-slate-600">This appointment does not accept new payments.</p>}
      {Number(invoice.fee) === 0 && status === 'unpaid' && <p className="rounded-xl bg-spandan-50 p-4">No consultation payment is required.</p>}
      <div className="flex flex-wrap gap-3">
        {patient && invoice.can_pay && invoice.online_enabled && !(checkoutResult === 'success' && status === 'pending') && <button disabled={busy} className="btn-primary" onClick={() => void act(async () => { const response = await apiClient.post(`/payments/appointment/${selected}/checkout`); window.location.assign(response.data.data.url); })}><CreditCard className="h-4 w-4" />{busy ? 'Opening secure checkout…' : status === 'pending' ? 'Resume payment' : 'Pay consultation fee'}</button>}
        {invoice.payment && <button className="btn-secondary" disabled={busy} onClick={() => void act(async () => { await apiClient.post(`/payments/${invoice.payment!.id}/refresh`); await refreshInvoice(); await refreshList(); })}><RefreshCw className="h-4 w-4" />Refresh payment status</button>}
        {invoice.payment?.status === 'pending' && invoice.payment.provider === 'stripe' && <button disabled={busy} className="btn-secondary" onClick={() => { if (window.confirm('Cancel this pending checkout? Your appointment will stay booked.')) void act(async () => { await apiClient.post(`/payments/${invoice.payment!.id}/cancel-checkout`); setParams({ tab: 'billing', appointment_id: selected }, { replace: true }); await refreshInvoice(); await refreshList(); setMessage('Checkout cancelled. You can choose another payment method.'); }); }}>Cancel checkout</button>}
        {!patient && !invoice.payment && invoice.can_pay && <button disabled={busy} className="btn-primary" onClick={() => { if (window.confirm('Confirm that the consultation fee was received in cash?')) void act(async () => { await apiClient.post(`/payments/appointment/${selected}/cash`, { method: 'cash' }); await refreshInvoice(); await refreshList(); setMessage('Cash payment recorded.'); }); }}>Record cash received</button>}
        {invoice.payment && ['paid', 'refunded', 'refund_pending'].includes(status) && <button disabled={busy} className="btn-secondary" onClick={() => void act(async () => { setReceipt((await apiClient.get(`/payments/${invoice.payment!.id}/receipt`)).data.data); })}><FileText className="h-4 w-4" />View receipt</button>}
        {['doctor', 'administrator'].includes(user?.role || '') && status === 'paid' && invoice.appointment.status === 'cancelled' && <button disabled={busy} className="btn-danger" onClick={() => { if (window.confirm('Refund this cancelled consultation? Cash refunds must also be returned to the patient.')) void act(async () => { await apiClient.post(`/payments/${invoice.payment!.id}/refund`); setReceipt(null); await refreshInvoice(); await refreshList(); setMessage('Refund request processed.'); }); }}>Refund payment</button>}
      </div>
      {patient && invoice.can_pay && <div className="flex gap-2 text-sm text-slate-500"><ShieldCheck className="h-4 w-4 shrink-0 mt-0.5" /><p>{invoice.online_enabled ? 'Card details are entered securely on Stripe. Sandbox payments use test cards; no real funds are transferred.' : 'Online checkout is temporarily unavailable. Please pay at the chamber.'}</p></div>}
      {receipt && <article className="payment-receipt rounded-2xl border bg-white p-6 space-y-4"><div className="border-b pb-4"><h3 className="text-xl font-bold">{receipt.operator}</h3><p className="text-sm text-slate-500">Consultation receipt · {receipt.contact}</p></div><p className="text-xs text-slate-500 break-all">Receipt #{receipt.receipt_number}</p><dl className="grid sm:grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-500">Patient</dt><dd>{receipt.patient_name}</dd></div><div><dt className="text-slate-500">Doctor</dt><dd>{receipt.doctor_name}</dd></div><div><dt className="text-slate-500">Chamber</dt><dd>{receipt.chamber_name}</dd></div><div><dt className="text-slate-500">Appointment</dt><dd>{date(receipt.session_date)} · Serial {receipt.serial_number}</dd></div><div><dt className="text-slate-500">Payment method</dt><dd>{receipt.provider === 'stripe' ? 'Card · Stripe' : receipt.provider === 'cash' ? 'Cash' : 'Recorded payment'}</dd></div><div><dt className="text-slate-500">Status</dt><dd>{labels[receipt.status] || receipt.status}</dd></div></dl><p className="border-t pt-4 text-2xl font-bold">{money(receipt.amount, receipt.currency)}</p>{receipt.paid_at && <p className="text-xs text-slate-500">Paid {new Date(receipt.paid_at).toLocaleString('en-GB', { timeZone: 'Asia/Dhaka' })} (Dhaka)</p>}{receipt.is_test && <p className="text-xs text-slate-500">Sandbox transaction. No real funds transferred.</p>}<button className="btn-secondary print:hidden" onClick={() => { document.body.classList.add('printing-receipt'); window.print(); document.body.classList.remove('printing-receipt'); }}>Print receipt</button></article>}
    </>}
  </section>;
}
