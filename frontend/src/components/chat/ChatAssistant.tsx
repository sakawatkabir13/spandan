import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Loader2, MessageCircle, Plus, Send, ShieldCheck, Square, Trash2, X } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { ChatAction, ChatMessage, Conversation, safeChatLink, streamMessage, ToolCard } from '../../api/chat';
import { useAuth } from '../../context/AuthContext';
import { Modal } from '../common/Modal';

const label = (value: string) => value.replace(/^propose_/, '').replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());

function Details({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value == null || depth > 4) return null;
  if (typeof value !== 'object') return <span className="break-words [overflow-wrap:anywhere]">{typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}</span>;
  if (Array.isArray(value)) return <div className="space-y-2">{value.map((item, index) => <div key={index} className="border-l-2 border-slate-200 pl-2"><Details value={item} depth={depth + 1} /></div>)}</div>;
  const entries = Object.entries(value as Record<string, unknown>).filter(([key, item]) => item != null && !['id', 'href', 'source_url', 'action', 'arguments', 'roster', 'existing_sessions', 'next_offset', 'timezone', 'error_code'].includes(key) && !key.endsWith('_id'));
  return <dl className="space-y-1.5 text-xs">{entries.map(([key, item]) => <div key={key} className="min-w-0"><dt className="font-semibold text-slate-600">{label(key)}</dt><dd className="text-slate-800"><Details value={item} depth={depth + 1} /></dd></div>)}</dl>;
}

function ActionCard({ action, update, report }: { action: ChatAction; update: (action: ChatAction) => void; report: (text: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [verify, setVerify] = useState(false);
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [verifyError, setVerifyError] = useState('');
  const expired = new Date(action.expires_at).getTime() <= Date.now();
  const pending = action.status === 'pending' && !expired;
  const confirm = async (token?: string) => {
    setBusy(true); setVerifyError('');
    try {
      const response = await apiClient.post(`/chat/actions/${action.id}/confirm`, { step_up_token: token }, { timeout: 45000 });
      update(response.data.data); setVerify(false); setPassword(''); setCode('');
    } catch (error) {
      const message = errorMessage(error); report(message); setVerifyError(message);
      try { const response = await apiClient.get(`/chat/actions/${action.id}`); update(response.data.data); } catch { /* Keep the last known status. */ }
    } finally { setBusy(false); }
  };
  const cancel = async () => {
    setBusy(true);
    try { const response = await apiClient.post(`/chat/actions/${action.id}/cancel`); update(response.data.data); }
    catch (error) { report(errorMessage(error)); } finally { setBusy(false); }
  };
  const verifyAndConfirm = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setVerifyError('');
    try {
      const response = await apiClient.post('/chat/step-up', { action_id: action.id, password, code: code || undefined });
      const token = response.data.data.step_up_token;
      setPassword(''); setCode('');
      await confirm(token);
    } catch (error) { setVerifyError(errorMessage(error)); setBusy(false); }
  };
  const link = safeChatLink(action.result?.checkout_url || action.result?.href);
  return <div className="rounded-xl border border-spandan-200 bg-white p-3 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-sm">{label(action.name)}</strong><span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold">{action.status === 'pending' && expired ? 'Expired' : label(action.status)}</span></div>
    {action.status !== 'succeeded' && <><Details value={action.summary} />
      <div className="rounded-lg bg-amber-50 p-2 text-xs text-amber-900">{action.name === 'propose_cash_payment' ? 'Confirm only if the chamber has already received this cash.' : action.name === 'propose_refund' ? 'This refunds the full eligible payment. Recording a cash refund does not physically return money.' : 'Review the person, session and fee carefully. No change occurs until you confirm.'}</div></>}
    {action.result && <p role="status" className="text-sm text-spandan-800">{action.result.message}</p>}
    {link && <a href={link} className="inline-flex rounded-lg bg-spandan-600 px-3 py-2 text-sm font-semibold text-white">{action.result?.checkout_url ? 'Continue to secure payment' : 'View appointment'}</a>}
    <div className="flex flex-wrap gap-2">
      {(pending || action.status === 'confirmed') && <button type="button" disabled={busy} onClick={() => action.requires_step_up && pending ? setVerify(true) : void confirm()} className="inline-flex items-center gap-1.5 rounded-lg bg-spandan-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}{action.status === 'confirmed' ? 'Check and retry' : action.requires_step_up ? 'Verify & confirm' : 'Confirm'}</button>}
      {pending && <button type="button" disabled={busy} onClick={() => void cancel()} className="rounded-lg border px-3 py-2 text-sm">Cancel proposal</button>}
      {action.status === 'confirmed' && <button type="button" disabled={busy} onClick={async () => { try { const response = await apiClient.get(`/chat/actions/${action.id}`); update(response.data.data); } catch (error) { report(errorMessage(error)); } }} className="rounded-lg border px-3 py-2 text-sm">Refresh status</button>}
    </div>
    <Modal isOpen={verify} onClose={() => { if (!busy) { setVerify(false); setPassword(''); setCode(''); } }} title="Verify this action" maxWidth="sm">
      <form onSubmit={verifyAndConfirm} className="space-y-4">
        <p className="text-sm text-slate-600">Verify {label(action.name).toLowerCase()} for the exact details shown on the card. Your credentials go directly to Spandan and are never sent to the AI.</p>
        {verifyError && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{verifyError}</p>}
        <label className="block text-sm font-medium">Password<input autoFocus autoComplete="current-password" type="password" required maxLength={128} value={password} onChange={e => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border p-2.5" /></label>
        <label className="block text-sm font-medium">Authenticator code, if enabled<input autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} className="mt-1 w-full rounded-lg border p-2.5" /></label>
        <button disabled={busy} className="w-full rounded-lg bg-spandan-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{busy ? 'Verifying…' : 'Verify and confirm this action'}</button>
      </form>
    </Modal>
  </div>;
}

function ResultCard({ card, update, report, ask }: { card: ToolCard; update: (action: ChatAction) => void; report: (text: string) => void; ask: (text: string) => void }) {
  if (card.data.proposal) return <ActionCard action={card.data.proposal} update={update} report={report} />;
  const items = card.data.items || [card.data];
  return <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-3">
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label(card.tool)}</p>
    {!items.length && <p className="text-sm text-slate-500">No matching results found.</p>}
    {items.map((item, index) => {
      const href = safeChatLink(item.href);
      return <div key={index} className="min-w-0 border-t border-slate-100 pt-2 first:border-0"><Details value={item} />{href && <a href={href} className="mt-2 inline-block text-sm font-semibold text-spandan-700 underline">Open in Spandan</a>}</div>;
    })}
    {card.data.next_offset != null && <button onClick={() => ask(`Show the next page for ${label(card.tool).toLowerCase()}, using offset ${card.data.next_offset}. Keep my previous filters.`)} className="text-sm font-semibold text-spandan-700 underline">Show more</button>}
  </div>;
}

export function ChatAssistant() {
  const { user, isAuthenticated } = useAuth();
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [consent, setConsent] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const alive = useRef(true);
  const reloadList = async () => { const response = await apiClient.get('/chat/conversations'); if (alive.current) setConversations(response.data.data); };
  useEffect(() => {
    alive.current = true;
    setOpen(false); setEnabled(false); setConversationId(null); setMessages([]); setConsent(false);
    if (isAuthenticated) apiClient.get('/service-capabilities').then(response => { if (alive.current) setEnabled(Boolean(response.data.data.chat)); }).catch(() => {});
    return () => { alive.current = false; abort.current?.abort(); };
  }, [isAuthenticated, user?.id]);
  useEffect(() => { if (open && enabled) { void reloadList().catch(() => {}); inputRef.current?.focus(); } }, [open, enabled]);
  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight }); }, [messages, progress]);
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panel.current?.focus();
    const listener = (event: KeyboardEvent) => {
      const dialogs = document.querySelectorAll('[role="dialog"][aria-modal="true"]');
      if (dialogs.length && dialogs[dialogs.length - 1] !== panel.current) return;
      if (event.key === 'Escape') setOpen(false);
      if (event.key !== 'Tab' || !panel.current) return;
      const controls = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href]'));
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', listener);
    return () => { document.body.style.overflow = previous; document.removeEventListener('keydown', listener); launcher.current?.focus(); };
  }, [open]);
  const loadConversation = async (id: string) => {
    if (busy) return;
    setError('');
    try { const response = await apiClient.get(`/chat/conversations/${id}`); setConversationId(id); setMessages(response.data.data.messages); setConsent(true); }
    catch (e) { setError(errorMessage(e)); }
  };
  const send = async (text = input) => {
    if (busy || !text.trim() || (!conversationId && !consent)) return;
    setBusy(true); setError(''); setProgress('Connecting…');
    let id = conversationId;
    const original = text;
    const controller = new AbortController(); abort.current = controller;
    try {
      if (!id) { const response = await apiClient.post('/chat/conversations', { provider_consent: true }); id = response.data.data.id; setConversationId(id); void reloadList(); }
      setInput('');
      setMessages(previous => [...previous, { role: 'user', text }, { role: 'assistant', text: '', cards: [] }]);
      let streamError = '';
      await streamMessage(id!, text, crypto.randomUUID(), controller.signal, (type, data) => {
        if (!alive.current) return;
        if (type === 'progress' || type === 'tool_start') setProgress(data.message);
        if (type === 'text') setMessages(previous => previous.map((m, index) => index === previous.length - 1 ? { ...m, text: data.text } : m));
        if (type === 'text_delta') setMessages(previous => previous.map((m, index) => index === previous.length - 1 ? { ...m, text: m.text + data.text } : m));
        if (type === 'tool_result' || type === 'proposal') setMessages(previous => previous.map((m, index) => index === previous.length - 1 ? { ...m, cards: [...(m.cards || []), data] } : m));
        if (type === 'error') { streamError = data.message; setError(data.message); }
      });
      if (streamError) setInput(original);
    } catch (e: any) {
      if (e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') { setError(e instanceof Error && !(e as any).response ? e.message : errorMessage(e)); setInput(original); }
    } finally { if (alive.current) { setBusy(false); setProgress(''); } abort.current = null; }
  };
  const stop = async () => {
    abort.current?.abort();
    if (conversationId) { try { await apiClient.post(`/chat/conversations/${conversationId}/stop`); } catch (e) { setError(errorMessage(e)); } }
    setBusy(false); setProgress('');
  };
  const updateAction = (action: ChatAction) => setMessages(previous => previous.map(m => ({ ...m, cards: m.cards?.map(card => card.data.proposal?.id === action.id ? { ...card, data: { ...card.data, proposal: action } } : card) })));
  const prompts = user?.role === 'patient' ? ['Find a doctor in Dhaka', 'Show my upcoming appointments', 'Show my payment status'] : user?.role === 'administrator' ? ['Show the operational summary', 'Show pending doctor approvals', 'Help me manage assistant permissions'] : ['Show my upcoming sessions', 'Show my appointment roster', 'Help me manage the queue'];
  if (!enabled || !isAuthenticated) return null;
  return <>
    <button ref={launcher} type="button" aria-label="Open Spandan Assistant" aria-expanded={open} onClick={() => setOpen(true)} className={`fixed right-4 ${user?.role === 'patient' ? 'bottom-[calc(5rem+env(safe-area-inset-bottom))] lg:bottom-6' : 'bottom-6'} z-40 flex items-center gap-2 rounded-full bg-spandan-700 px-4 py-3 text-sm font-semibold text-white shadow-lg hover:bg-spandan-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-spandan-600`}><MessageCircle className="h-5 w-5" /><span className="hidden sm:inline">Ask Spandan</span></button>
    {open && createPortal(<div className="fixed inset-0 z-50 bg-slate-900/35 sm:bg-transparent" onMouseDown={event => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section ref={panel} role="dialog" aria-modal="true" aria-labelledby="spandan-chat-title" tabIndex={-1} className="absolute inset-0 flex min-w-0 flex-col bg-white shadow-2xl sm:inset-auto sm:bottom-5 sm:right-5 sm:h-[min(760px,calc(100dvh-2.5rem))] sm:w-[440px] sm:max-w-[calc(100vw-2.5rem)] sm:rounded-2xl sm:border sm:border-slate-200 overflow-hidden">
        <header className="flex shrink-0 items-center gap-3 border-b bg-spandan-700 px-4 py-3 text-white"><MessageCircle className="h-6 w-6 shrink-0" /><div className="min-w-0 flex-1"><h2 id="spandan-chat-title" className="font-semibold">Spandan Assistant</h2><p className="text-xs text-spandan-100">Appointments & support · English</p></div><button aria-label="Close assistant" onClick={() => setOpen(false)} className="rounded-lg p-2 hover:bg-white/10"><X className="h-5 w-5" /></button></header>
        <div className="flex shrink-0 gap-2 border-b bg-slate-50 px-3 py-2">
          <select aria-label="Conversation history" disabled={busy} value={conversationId || ''} onChange={e => { if (e.target.value) void loadConversation(e.target.value); }} className="min-w-0 flex-1 rounded-lg border bg-white px-2 text-sm"><option value="">Conversation history</option>{conversations.map(c => <option key={c.id} value={c.id}>{new Date(c.created_at).toLocaleDateString('en-GB')} · {c.title}</option>)}</select>
          <button aria-label="New conversation" disabled={busy} onClick={() => { setConversationId(null); setMessages([]); setInput(''); setError(''); setConsent(false); }} className="rounded-lg border bg-white p-2"><Plus className="h-4 w-4" /></button>
          <button aria-label="Delete conversation" disabled={!conversationId || busy} onClick={() => setDeleteOpen(true)} className="rounded-lg border bg-white p-2 text-red-700 disabled:opacity-40"><Trash2 className="h-4 w-4" /></button>
        </div>
        <div ref={list} className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-4">
          {!messages.length && <div className="space-y-4"><p className="text-sm text-slate-600">I can help you find doctors, manage appointments and use Spandan. Changes require your confirmation. Please keep medical details and passwords out of chat.</p><div className="flex flex-col gap-2">{prompts.map(prompt => <button key={prompt} onClick={() => { setInput(prompt); inputRef.current?.focus(); }} className="rounded-xl border border-spandan-200 p-3 text-left text-sm text-spandan-800 hover:bg-spandan-50">{prompt}</button>)}</div></div>}
          {messages.map((message, index) => <article key={message.id || index} aria-label={`${message.role === 'user' ? 'You' : 'Assistant'} message`} className={`min-w-0 space-y-2 ${message.role === 'user' ? 'ml-8 rounded-xl bg-spandan-50 p-3' : 'mr-1'}`}><p className="text-[11px] font-semibold uppercase text-slate-500">{message.role === 'user' ? 'You' : 'Spandan'}</p>{message.text && <p className="whitespace-pre-wrap break-words text-sm [overflow-wrap:anywhere]">{message.text}</p>}{message.cards?.map((card, cardIndex) => <ResultCard key={cardIndex} card={card} update={updateAction} report={setError} ask={text => void send(text)} />)}</article>)}
          {busy && <p role="status" aria-live="polite" className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />{progress || 'Preparing your response…'}</p>}
        </div>
        <footer className="shrink-0 space-y-2 border-t bg-white p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          {error && <p role="alert" className="rounded-lg bg-red-50 p-2 text-xs text-red-700">{error}</p>}
          {!conversationId && <label className="flex items-start gap-2 text-xs leading-relaxed text-slate-600"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} className="mt-0.5 shrink-0" /><span>I agree to Amazon Bedrock processing my support messages. Chats are saved for 30 days and can be deleted.</span></label>}
          <form onSubmit={event => { event.preventDefault(); void send(); }} className="flex items-end gap-2">
            <textarea ref={inputRef} aria-label="Message Spandan Assistant in English" placeholder="Ask in English…" maxLength={4000} value={input} rows={2} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} className="max-h-36 min-w-0 flex-1 resize-y rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-spandan-500 focus:outline-none focus:ring-2 focus:ring-spandan-100" />
            {busy ? <button type="button" aria-label="Stop reply" onClick={() => void stop()} className="rounded-xl border p-3"><Square className="h-5 w-5" /></button> : <button type="submit" aria-label="Send message" disabled={!input.trim() || (!conversationId && !consent)} className="rounded-xl bg-spandan-700 p-3 text-white disabled:opacity-40"><Send className="h-5 w-5" /></button>}
          </form>
          <p className="flex items-center gap-1 text-[10px] text-slate-500"><ShieldCheck className="h-3 w-3" />AI can make mistakes. Review confirmation details.</p>
        </footer>
      </section>
    </div>, document.body)}
    <Modal isOpen={deleteOpen} onClose={() => setDeleteOpen(false)} title="Delete this conversation?" maxWidth="sm"><p className="mb-4 text-sm text-slate-600">This removes its messages and cancels unconfirmed proposals. Completed appointment and payment records remain available in Spandan.</p><button onClick={async () => { try { await apiClient.delete(`/chat/conversations/${conversationId}`); setConversationId(null); setMessages([]); setConsent(false); setDeleteOpen(false); await reloadList(); } catch (e) { setError(errorMessage(e)); setDeleteOpen(false); } }} className="w-full rounded-lg bg-red-600 px-4 py-3 font-semibold text-white">Delete conversation</button></Modal>
  </>;
}
