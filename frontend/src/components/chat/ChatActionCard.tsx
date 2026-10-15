import React, { useEffect, useState } from 'react';
import { AlertCircle, Check, CheckCircle2, Clock3, Loader2, LockKeyhole, XCircle } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { ChatAction, safeChatLink } from '../../api/chat';
import { Modal } from '../common/Modal';
import { ChatDetails, ChatLink, readableName } from './ChatContent';

export function ChatActionCard({ action, update, onNavigate }: { action: ChatAction; update: (action: ChatAction) => void; onNavigate: () => void }) {
  const [busy, setBusy] = useState(false);
  const [verify, setVerify] = useState(false);
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [verifyError, setVerifyError] = useState('');
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (action.status !== 'pending') return; const timer = setInterval(() => setNow(Date.now()), 5000); return () => clearInterval(timer); }, [action.status]);
  const expired = new Date(action.expires_at).getTime() <= now;
  const pending = action.status === 'pending' && !expired;
  const complete = action.status === 'succeeded';
  const status = action.status === 'pending' ? expired ? 'Expired' : 'Needs your confirmation' : ({ succeeded: 'Completed', confirmed: 'Checking outcome', cancelled: 'Cancelled', failed: 'Could not complete', stale: 'Details changed' } as Record<string, string>)[action.status] || readableName(action.status);
  const confirm = async (token?: string) => {
    setBusy(true); setError(''); setVerifyError('');
    try {
      const response = await apiClient.post(`/chat/actions/${action.id}/confirm`, { step_up_token: token }, { timeout: 45000 });
      update(response.data.data); setVerify(false); setPassword(''); setCode('');
    } catch (e) {
      const message = errorMessage(e); setError(message); setVerifyError(message);
      try { update((await apiClient.get(`/chat/actions/${action.id}`)).data.data); } catch { /* Keep the last known status until it can be verified. */ }
    } finally { setBusy(false); }
  };
  const cancel = async () => {
    setBusy(true); setError('');
    try { update((await apiClient.post(`/chat/actions/${action.id}/cancel`)).data.data); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };
  const verifyAndConfirm = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setVerifyError('');
    try {
      const response = await apiClient.post('/chat/step-up', { action_id: action.id, password, code: code || undefined });
      setPassword(''); setCode('');
      await confirm(response.data.data.step_up_token);
    } catch (e) { setVerifyError(errorMessage(e)); setBusy(false); }
  };
  const link = safeChatLink(action.result?.checkout_url || action.result?.href);
  const linkText = action.result?.checkout_url ? 'Continue to secure payment' : link?.includes('payment') || link?.includes('billing') ? 'View payment details' : link?.includes('/queue') ? 'Open queue' : link?.includes('/users') ? 'View account' : link?.includes('verification') ? 'View doctor status' : 'View appointment';
  return <section className={`chat-result-card ${complete ? 'border-spandan-200' : 'border-amber-200/80'}`} aria-label={readableName(action.name)}>
    <header className={`space-y-2 border-b px-4 py-3 ${complete ? 'border-spandan-100 bg-spandan-50' : 'border-amber-100 bg-amber-50/60'}`}>
      <div className="flex items-start gap-2.5">{complete ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-spandan-700" /> : pending ? <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" /> : <Clock3 className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" />}<div className="min-w-0"><h3 className="text-sm font-bold text-slate-900">{readableName(action.name)}</h3><p className="mt-1 text-[11px] font-medium text-slate-500">{status}</p></div></div>
    </header>
    <div className="space-y-4 p-4">
      {complete ? <><p role="status" className="text-sm font-medium leading-relaxed text-spandan-800">{action.result?.message || 'Spandan has verified that this action completed.'}</p>{action.result?.serial_number != null && <p className="rounded-xl bg-spandan-50 px-3 py-2 text-sm font-semibold text-spandan-800">Your serial: #{String(action.result.serial_number)}</p>}<details className="rounded-xl border border-slate-200 bg-slate-50/60 p-3"><summary className="text-xs font-semibold text-slate-600">View confirmed details</summary><div className="mt-3"><ChatDetails value={action.summary} /></div></details></> : <>
        <ChatDetails value={action.summary} />
        {pending && <div className="rounded-xl border border-amber-100 bg-amber-50/70 p-3 text-xs leading-relaxed text-amber-900">{action.name === 'propose_cash_payment' ? 'Confirm only if the chamber has already received this cash.' : action.name === 'propose_refund' ? 'This refunds the full eligible payment. Recording a cash refund does not physically return money.' : 'Check the person, date, session, and fee. Nothing changes until you press Confirm.'}</div>}
        {expired && action.status === 'pending' && <p className="flex items-start gap-2 text-xs leading-relaxed text-slate-500"><Clock3 className="mt-0.5 h-4 w-4 shrink-0" />This proposal expired. Ask for a new proposal to review the current details.</p>}
        {action.status === 'stale' && <p className="text-xs leading-relaxed text-amber-900">The booking, fee, availability, or permissions changed. Ask for a new proposal before continuing.</p>}
        {action.status === 'confirmed' && <p className="text-xs leading-relaxed text-amber-900">Your confirmation was received. Check its outcome before starting another request. Retrying checks the same operation.</p>}
        {action.status === 'cancelled' && <p className="flex items-center gap-2 text-xs text-slate-500"><XCircle className="h-4 w-4" />You cancelled this proposal. No action was executed from it.</p>}
        {action.result?.message && <p role="status" className="text-sm leading-relaxed text-slate-700">{action.result.message}</p>}
      </>}
      {error && <p role="alert" className="flex items-start gap-2 rounded-xl bg-red-50 p-3 text-xs leading-relaxed text-red-800"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</p>}
      {link && <ChatLink href={link} onNavigate={onNavigate} className="btn-primary w-full text-xs">{linkText}</ChatLink>}
      {(pending || action.status === 'confirmed') && <div className="flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => action.requires_step_up && pending ? setVerify(true) : void confirm()} className="btn-primary flex-1 text-xs">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}{action.status === 'confirmed' ? 'Check and retry' : action.requires_step_up ? 'Verify & confirm' : 'Confirm'}</button>{pending ? <button type="button" disabled={busy} onClick={() => void cancel()} className="btn-secondary text-xs">Cancel proposal</button> : <button type="button" disabled={busy} onClick={async () => { try { update((await apiClient.get(`/chat/actions/${action.id}`)).data.data); setError(''); } catch (e) { setError(errorMessage(e)); } }} className="btn-secondary text-xs">Refresh status</button>}</div>}
      {pending && <p className="flex items-center gap-1.5 text-[10px] text-slate-400"><Clock3 className="h-3 w-3" />Expires at {new Date(action.expires_at).toLocaleTimeString('en-GB', { timeZone: 'Asia/Dhaka', hour: '2-digit', minute: '2-digit' })} · Dhaka time</p>}
    </div>
    <Modal isOpen={verify} onClose={() => { if (!busy) { setVerify(false); setPassword(''); setCode(''); setVerifyError(''); } }} title="Verify this action" maxWidth="sm"><form onSubmit={verifyAndConfirm} className="space-y-4"><p className="text-sm leading-relaxed text-slate-600">Verify {readableName(action.name).toLowerCase()} for the details shown on the card. Your credentials go directly to Spandan and are never sent to the AI.</p>{verifyError && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{verifyError}</p>}<label className="block text-sm font-medium">Password<input autoFocus autoComplete="current-password" type="password" required maxLength={128} value={password} onChange={e => setPassword(e.target.value)} className="input-field mt-2" /></label><label className="block text-sm font-medium">Authenticator code, if enabled<input autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} className="input-field mt-2" /></label><button disabled={busy} className="btn-primary w-full text-sm">{busy ? 'Verifying…' : 'Verify and confirm this action'}</button></form></Modal>
  </section>;
}
