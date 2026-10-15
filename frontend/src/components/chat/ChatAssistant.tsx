import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Activity, AlertCircle, ArrowDown, ArrowUpRight, CalendarDays, Check, ChevronDown, Copy, History, Loader2, MessageCircle, Plus, RefreshCw, Search, Send, ShieldCheck, Sparkles, Square, Trash2, Wallet, X } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { ChatAction, ChatMessage, Conversation, streamMessage } from '../../api/chat';
import { useAuth } from '../../context/AuthContext';
import { Modal } from '../common/Modal';
import { ChatActionCard } from './ChatActionCard';
import { ChatResultCard, ChatText, readableName } from './ChatContent';

const progressText = (name: string) => ({ search_doctors: 'Finding doctors for your request…', list_sessions: 'Checking published sessions…', list_appointments: 'Checking your appointments…', appointment_details: 'Opening the appointment details…', queue_status: 'Checking the current queue…', list_payments: 'Checking payment information…', payment_details: 'Checking this payment…', receipt: 'Looking up your receipt…', help: 'Finding the right guidance…', list_waitlist: 'Checking waitlist updates…' } as Record<string, string>)[name] || (name.startsWith('propose_') ? 'Preparing the details for your confirmation…' : `Checking ${readableName(name).toLowerCase()}…`);
function CopyReply({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => { if (!copied) return; const timer = setTimeout(() => setCopied(false), 2000); return () => clearTimeout(timer); }, [copied]);
  return <span className="inline-flex items-center gap-2"><button type="button" aria-label={copied ? 'Reply copied' : 'Copy reply'} className="chat-icon-button !min-h-8 !min-w-8 !p-1.5 text-slate-400" onClick={async () => { try { await navigator.clipboard.writeText(text); setCopied(true); setFailed(false); } catch { setFailed(true); } }}>{copied ? <Check className="h-3.5 w-3.5 text-spandan-700" /> : <Copy className="h-3.5 w-3.5" />}</button><span role="status" className="text-[10px] text-slate-500">{copied ? 'Copied' : failed ? 'Select the reply text to copy it.' : ''}</span></span>;
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
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [remoteGenerating, setRemoteGenerating] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [unread, setUnread] = useState(false);
  const [viewport, setViewport] = useState<{ height: number; top: number } | null>(null);
  const abort = useRef<AbortController | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const alive = useRef(true);
  const actor = useRef(0);
  const sending = useRef(false);
  const loading = useRef(false);
  const turn = useRef(0);
  const stickToBottom = useRef(true);
  const isWorking = busy || remoteGenerating;
  const reloadList = async () => { const scope = actor.current; const response = await apiClient.get('/chat/conversations'); if (alive.current && scope === actor.current) setConversations(response.data.data); };
  useEffect(() => {
    alive.current = true; actor.current++;
    setOpen(false); setEnabled(false); setConversationId(null); setMessages([]); setConsent(false); setBusy(false); setRemoteGenerating(false); setError(''); setInput(''); setLoadingHistory(false); setConversations([]); setDeleteOpen(false); setDeleting(false);
    loading.current = false; sending.current = false; turn.current++;
    const scope = actor.current;
    if (isAuthenticated) void apiClient.get('/service-capabilities').then(response => { if (alive.current && scope === actor.current) setEnabled(Boolean(response.data.data.chat)); }).catch(() => {});
    return () => { alive.current = false; actor.current++; turn.current++; abort.current?.abort(); };
  }, [isAuthenticated, user?.id]);
  useEffect(() => { if (open && enabled) void reloadList().catch(() => {}); }, [open, enabled]);
  useEffect(() => {
    if (!open) return;
    const resize = () => { const view = window.visualViewport; setViewport(window.innerWidth < 640 && view ? { height: view.height, top: view.offsetTop } : null); };
    resize(); window.addEventListener('resize', resize); window.visualViewport?.addEventListener('resize', resize); window.visualViewport?.addEventListener('scroll', resize);
    return () => { window.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('scroll', resize); };
  }, [open]);
  useLayoutEffect(() => {
    if (!open || !list.current) return;
    if (stickToBottom.current) list.current.scrollTop = list.current.scrollHeight;
    else setUnread(true);
  }, [messages, progress, open]);
  useLayoutEffect(() => { const field = inputRef.current; if (field) { field.style.height = 'auto'; field.style.height = `${Math.min(field.scrollHeight, 144)}px`; } }, [input, open]);
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
      const controls = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], summary, [tabindex="0"]')).filter(element => !element.closest('details:not([open])') || element.tagName === 'SUMMARY');
      const first = controls[0], last = controls[controls.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', listener);
    return () => { document.body.style.overflow = previous; document.removeEventListener('keydown', listener); launcher.current?.focus(); };
  }, [open]);
  const loadConversation = async (id: string) => {
    if (sending.current || loading.current) return;
    const scope = actor.current; loading.current = true; setLoadingHistory(true); setError('');
    try { const response = await apiClient.get(`/chat/conversations/${id}`); if (!alive.current || scope !== actor.current) return; setConversationId(id); setMessages(response.data.data.messages); setRemoteGenerating(Boolean(response.data.data.generating)); setConsent(true); stickToBottom.current = true; setUnread(false); }
    catch (e) { if (alive.current && scope === actor.current) setError(errorMessage(e)); }
    finally { if (scope === actor.current) { loading.current = false; if (alive.current) setLoadingHistory(false); } }
  };
  useEffect(() => {
    if (!open || !remoteGenerating || !conversationId || busy) return;
    let cancelled = false; let pending = false; const scope = actor.current;
    const refresh = async () => { if (pending || document.hidden) return; pending = true; try { const response = await apiClient.get(`/chat/conversations/${conversationId}`); if (!cancelled && scope === actor.current) { setMessages(response.data.data.messages); setRemoteGenerating(Boolean(response.data.data.generating)); } } catch (e) { if (!cancelled && scope === actor.current) { setError(errorMessage(e)); setRemoteGenerating(false); } } finally { pending = false; } };
    const timer = setInterval(() => void refresh(), 4000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [open, remoteGenerating, conversationId, busy]);
  const send = async (text = input) => {
    if (sending.current || loading.current || remoteGenerating || !text.trim() || (!conversationId && !consent)) return;
    sending.current = true; const sequence = ++turn.current;
    setBusy(true); setError(''); setProgress('Connecting to Spandan…'); stickToBottom.current = true; setUnread(false);
    let id = conversationId;
    const original = text.trim();
    const controller = new AbortController(); abort.current = controller;
    const assistantId = crypto.randomUUID();
    const current = () => alive.current && turn.current === sequence;
    const editReply = (change: (message: ChatMessage) => ChatMessage) => setMessages(previous => previous.map(message => message.id === assistantId ? change(message) : message));
    try {
      if (!id) { const response = await apiClient.post('/chat/conversations', { provider_consent: true }); if (!current()) return; id = response.data.data.id; setConversationId(id); void reloadList().catch(() => {}); }
      setInput('');
      setMessages(previous => [...previous, { id: crypto.randomUUID(), role: 'user', text: original, created_at: new Date().toISOString() }, { id: assistantId, role: 'assistant', text: '', cards: [], delivery: 'streaming' }]);
      let streamError = '';
      await streamMessage(id!, original, crypto.randomUUID(), controller.signal, (type, data) => {
        if (!current()) return;
        if (type === 'progress') setProgress(data.message);
        if (type === 'tool_start') { setProgress(progressText(data.name)); editReply(message => ({ ...message, text: '' })); }
        if (type === 'text') editReply(message => ({ ...message, text: data.text }));
        if (type === 'text_delta') { setProgress('Writing your answer…'); editReply(message => ({ ...message, text: message.text + data.text })); }
        if (type === 'tool_result' || type === 'proposal') editReply(message => ({ ...message, cards: [...(message.cards || []), data] }));
        if (type === 'error') { streamError = data.message; setError(data.message); editReply(message => ({ ...message, delivery: 'error' })); }
      });
      if (current()) { editReply(message => ({ ...message, delivery: streamError ? 'error' : 'complete' })); if (streamError) setInput(original); void reloadList().catch(() => {}); }
    } catch (e: any) {
      if (current() && e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') { setError(e instanceof Error && !('response' in e) ? e.message : errorMessage(e)); setInput(original); editReply(message => ({ ...message, delivery: 'error' })); }
    } finally { if (current()) { sending.current = false; setBusy(false); setProgress(''); } if (abort.current === controller) abort.current = null; }
  };
  const stop = async () => {
    const sequence = ++turn.current;
    abort.current?.abort(); setProgress('Stopping the reply…');
    setMessages(previous => previous.map(message => message.delivery === 'streaming' ? { ...message, delivery: 'stopped' } : message));
    try { if (conversationId) await apiClient.post(`/chat/conversations/${conversationId}/stop`); }
    catch (e) { if (alive.current && sequence === turn.current) setError(errorMessage(e)); }
    finally { if (alive.current && sequence === turn.current) { sending.current = false; setBusy(false); setRemoteGenerating(false); setProgress(''); } }
  };
  const updateAction = (action: ChatAction) => setMessages(previous => previous.map(message => ({ ...message, cards: message.cards?.map(card => card.data.proposal?.id === action.id ? { ...card, data: { ...card.data, proposal: action } } : card) })));
  const prompts = user?.role === 'patient' ? [{ text: 'Find a doctor in Dhaka', icon: Search }, { text: 'Show my upcoming appointments', icon: CalendarDays }, { text: 'Show my payment status', icon: Wallet }] : user?.role === 'administrator' ? [{ text: 'Show the operational summary', icon: Activity }, { text: 'Show pending doctor approvals', icon: ShieldCheck }, { text: 'Help me manage assistant permissions', icon: CalendarDays }] : [{ text: 'Show my upcoming sessions', icon: CalendarDays }, { text: 'Show my appointment roster', icon: Search }, { text: 'Help me manage the queue', icon: Activity }];
  const newConversation = () => { if (sending.current || loading.current || remoteGenerating) return; setConversationId(null); setMessages([]); setInput(''); setError(''); setConsent(false); setUnread(false); stickToBottom.current = true; inputRef.current?.focus(); };
  if (!enabled || !isAuthenticated) return null;
  return <>
    <button ref={launcher} type="button" aria-label="Open Spandan Assistant" aria-expanded={open} aria-controls="spandan-assistant-panel" onClick={() => setOpen(true)} className={`chat-launcher fixed right-4 ${user?.role === 'patient' ? 'bottom-[calc(5rem+env(safe-area-inset-bottom))] lg:bottom-6' : 'bottom-6'} z-40 inline-flex min-h-12 items-center gap-2.5 rounded-full px-4 py-3 text-sm font-semibold text-white`}><span className="relative"><MessageCircle className="h-5 w-5" /><span className="absolute -right-1 -top-1 h-2 w-2 rounded-full border border-spandan-800 bg-spandan-200" /></span><span className="hidden sm:inline">Ask Spandan</span></button>
    {open && createPortal(<div className="chat-overlay fixed inset-0 z-50 bg-slate-950/30 backdrop-blur-[2px] sm:bg-transparent sm:backdrop-blur-none" style={viewport ? { height: viewport.height, top: viewport.top, bottom: 'auto' } : undefined} onMouseDown={event => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section id="spandan-assistant-panel" ref={panel} role="dialog" aria-modal="true" aria-labelledby="spandan-chat-title" lang="en" tabIndex={-1} className="chat-panel absolute inset-0 flex min-w-0 flex-col overflow-hidden bg-white sm:inset-auto sm:bottom-5 sm:right-5 sm:h-[min(800px,calc(100dvh-2.5rem))] sm:w-[480px] sm:max-w-[calc(100vw-2.5rem)] sm:rounded-3xl">
        <header className="chat-header flex shrink-0 items-center gap-3 px-4 py-4 text-white sm:px-5"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/15 bg-white/10 text-spandan-200"><Activity className="h-6 w-6" /></span><div className="min-w-0 flex-1"><h2 id="spandan-chat-title" className="text-[15px] font-bold tracking-tight">Spandan Assistant</h2><p className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-300"><span className="h-1.5 w-1.5 rounded-full bg-spandan-300" />Appointments & support · English</p></div><button type="button" aria-label="Close assistant" onClick={() => setOpen(false)} className="chat-icon-button text-white/70 hover:!bg-white/10 hover:!text-white"><X className="h-5 w-5" /></button></header>
        <div className="flex shrink-0 items-center gap-2 border-b border-slate-100 bg-white px-3 py-2.5 sm:px-4"><div className="relative flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50 px-2.5 text-slate-500"><History className="h-4 w-4 shrink-0" /><select aria-label="Conversation history" disabled={isWorking || loadingHistory} value={conversationId || ''} onChange={e => { if (e.target.value) void loadConversation(e.target.value); }} className="min-h-10 w-full min-w-0 appearance-none bg-transparent pr-4 text-xs outline-none"><option value="">Recent conversations</option>{conversations.map(c => <option key={c.id} value={c.id}>{new Date(c.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'Asia/Dhaka' })} · {c.title}</option>)}</select><ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5" /></div><button type="button" aria-label="New conversation" title="New conversation" disabled={isWorking || loadingHistory} onClick={newConversation} className="chat-icon-button"><Plus className="h-4 w-4" /></button><button type="button" aria-label="Delete conversation" title="Delete conversation" disabled={!conversationId || isWorking || loadingHistory} onClick={() => setDeleteOpen(true)} className="chat-icon-button hover:!bg-red-50 hover:!text-red-700"><Trash2 className="h-4 w-4" /></button></div>
        <div className="relative flex min-h-0 flex-1 flex-col"><div ref={list} role="log" aria-label="Conversation messages" aria-live="off" onScroll={() => { const el = list.current; if (el) { stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 72; if (stickToBottom.current) setUnread(false); } }} className="chat-thread min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain px-4 py-5 sm:px-5">
          {loadingHistory && <p role="status" className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />Opening your conversation…</p>}
          {!messages.length && !loadingHistory && <div className="chat-welcome space-y-6 py-3"><div><span className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-spandan-100 bg-gradient-to-br from-white to-spandan-50 text-spandan-700 shadow-sm shadow-spandan-600/10"><Sparkles className="h-7 w-7" /></span><h3 className="text-[24px] font-bold leading-tight tracking-tight text-slate-900">How can I help you today?</h3><p className="mt-3 max-w-sm text-sm leading-relaxed text-slate-500">Find your doctor, stay on top of appointments, or get help using Spandan.</p></div><div className="space-y-2.5">{prompts.map(prompt => <button type="button" key={prompt.text} onClick={() => { setInput(prompt.text); inputRef.current?.focus(); }} className="chat-suggestion group"><span className="rounded-lg bg-spandan-50 p-2 text-spandan-700"><prompt.icon className="h-4 w-4" /></span><span className="min-w-0 flex-1">{prompt.text}</span><ArrowUpRight className="h-4 w-4 shrink-0 text-slate-300 transition group-hover:text-spandan-700" /></button>)}</div><p className="flex gap-2 text-xs leading-relaxed text-slate-500"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-spandan-700" />You stay in control. Every change needs your confirmation. Keep passwords and medical details out of chat.</p></div>}
          {messages.map(message => <article key={message.id || `${message.role}-${messages.indexOf(message)}`} aria-label={`${message.role === 'user' ? 'You' : 'Assistant'} message`} className={`chat-message min-w-0 ${message.role === 'user' ? 'ml-8 flex flex-col items-end' : 'space-y-3'}`}>
            {message.role === 'user' ? <><div className="chat-user-bubble max-w-full whitespace-pre-wrap rounded-2xl rounded-br-md px-4 py-3 text-sm leading-relaxed text-white [overflow-wrap:anywhere]">{message.text}</div><p className="mt-1.5 pr-1 text-[10px] text-slate-400">You{message.created_at ? ` · ${new Date(message.created_at).toLocaleTimeString('en-GB', { timeZone: 'Asia/Dhaka', hour: '2-digit', minute: '2-digit' })}` : ''}</p></> : <><div className="flex items-center gap-2"><span className="flex h-6 w-6 items-center justify-center rounded-lg bg-spandan-100 text-spandan-700"><Activity className="h-3.5 w-3.5" /></span><p className="text-[11px] font-semibold text-slate-500">Spandan</p></div>{message.text && <ChatText text={message.text} onNavigate={() => setOpen(false)} />}{message.cards?.map((card, index) => card.data.proposal ? <ChatActionCard key={card.data.proposal.id} action={card.data.proposal} update={updateAction} onNavigate={() => setOpen(false)} /> : <ChatResultCard key={`${card.tool}-${index}`} card={card} ask={text => void send(text)} onNavigate={() => setOpen(false)} />)}{message.delivery === 'stopped' && <p role="status" className="flex items-center gap-1.5 text-[11px] text-slate-500"><Square className="h-3 w-3" />Reply stopped. Confirmed actions keep their execution status.</p>}{message.text && message.delivery !== 'streaming' && <CopyReply text={message.text} />}</>}
          </article>)}
          {isWorking && <p role="status" aria-live="polite" className="flex items-center gap-2.5 text-xs text-slate-500"><span className="chat-thinking flex items-center gap-1" aria-hidden="true"><i /><i /><i /></span>{progress || (remoteGenerating ? 'Your reply is still processing. Checking for updates…' : 'Preparing your response…')}</p>}
        </div>{unread && <button type="button" onClick={() => { stickToBottom.current = true; setUnread(false); list.current?.scrollTo({ top: list.current.scrollHeight, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }} className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-lg shadow-slate-900/10">Latest response<ArrowDown className="h-3.5 w-3.5" /></button>}</div>
        <footer className="shrink-0 space-y-3 border-t border-slate-100 bg-white px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-4">
          {error && <div role="alert" className="rounded-xl border border-red-100 bg-red-50 px-3 py-2.5 text-xs leading-relaxed text-red-800"><p className="flex items-start gap-2"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</p>{conversationId && <button type="button" disabled={isWorking || loadingHistory} className="mt-2 inline-flex min-h-8 items-center gap-1.5 font-semibold underline underline-offset-2 disabled:opacity-50" onClick={() => void loadConversation(conversationId)}><RefreshCw className="h-3 w-3" />Reload conversation</button>}</div>}
          {!conversationId && <label className="flex items-start gap-2.5 rounded-xl border border-slate-200/80 bg-slate-50 px-3 py-2.5 text-[11px] leading-relaxed text-slate-500"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-spandan-700" /><span>I agree to Amazon Bedrock processing my support messages. Chats are saved for 30 days and can be deleted.</span></label>}
          <form onSubmit={event => { event.preventDefault(); void send(); }} className="chat-composer flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50/70 p-2 focus-within:border-spandan-400 focus-within:bg-white focus-within:ring-4 focus-within:ring-spandan-50"><textarea ref={inputRef} aria-label="Message Spandan Assistant in English" placeholder="Ask about doctors, visits, payments…" maxLength={4000} value={input} rows={1} disabled={loadingHistory} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} className="max-h-36 min-h-10 min-w-0 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm leading-5 text-slate-800 outline-none placeholder:text-slate-400" />{isWorking ? <button type="button" aria-label="Stop reply" onClick={() => void stop()} className="chat-icon-button mb-0.5 rounded-xl border border-slate-200 bg-white"><Square className="h-4 w-4" /></button> : <button type="submit" aria-label="Send message" disabled={loadingHistory || !input.trim() || (!conversationId && !consent)} className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-spandan-700 text-white shadow-sm shadow-spandan-600/20 transition hover:bg-spandan-800 disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"><Send className="h-4 w-4" /></button>}</form>
          <p className="flex items-center justify-center gap-1.5 text-[10px] text-slate-400"><ShieldCheck className="h-3 w-3" />AI can make mistakes. Review important details.</p>
        </footer>
      </section>
    </div>, document.body)}
    <Modal isOpen={deleteOpen} onClose={() => { if (!deleting) setDeleteOpen(false); }} title="Delete this conversation?" maxWidth="sm"><p className="mb-5 text-sm leading-relaxed text-slate-600">This removes its messages and cancels unconfirmed proposals. Completed appointment and payment records remain available in Spandan.</p><button type="button" disabled={deleting} onClick={async () => { const scope = actor.current; setDeleting(true); try { await apiClient.delete(`/chat/conversations/${conversationId}`); if (!alive.current || scope !== actor.current) return; setConversationId(null); setMessages([]); setConsent(false); setDeleteOpen(false); await reloadList(); } catch (e) { if (alive.current && scope === actor.current) { setError(errorMessage(e)); setDeleteOpen(false); } } finally { if (alive.current && scope === actor.current) setDeleting(false); } }} className="btn-danger w-full">{deleting ? 'Deleting…' : 'Delete conversation'}</button></Modal>
  </>;
}
