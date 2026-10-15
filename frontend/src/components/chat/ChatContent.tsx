import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowUpRight, CalendarDays, Clock3, CreditCard, FileText, MapPin, Search, ShieldCheck, Stethoscope } from 'lucide-react';
import { safeChatLink, ToolCard } from '../../api/chat';

const names: Record<string, string> = {
  search_doctors: 'Doctors', doctor_details: 'Doctor profile', list_specialties: 'Specialties', list_chambers: 'Chambers', list_sessions: 'Available sessions',
  list_appointments: 'Appointments', appointment_details: 'Appointment details', list_payments: 'Payments', payment_details: 'Payment details', receipt: 'Receipt',
  queue_status: 'Live queue', list_dependents: 'Family members', list_waitlist: 'Waitlist', list_assistant_assignments: 'Assistant access', admin_summary: 'Operations overview',
  list_users: 'Accounts', list_doctor_approvals: 'Doctor approvals', help: 'Helpful guidance',
  propose_book_appointment: 'Review your booking', propose_reschedule: 'Review your new session', propose_appointment_status: 'Review appointment update',
  propose_join_waitlist: 'Join this waitlist', propose_leave_waitlist: 'Leave this waitlist', propose_checkout: 'Review your payment', propose_cancel_checkout: 'Cancel this checkout',
  propose_create_session: 'Review new session', propose_update_session: 'Review session changes', propose_advance_queue: 'Advance the queue', propose_queue_delay: 'Update queue delay',
  propose_cash_payment: 'Record received cash', propose_refund: 'Review this refund', propose_assistant_permissions: 'Review assistant permissions', propose_doctor_verification: 'Review doctor status', propose_user_status: 'Review account access',
};
const fields: Record<string, string> = {
  full_name: 'Name', attendee_name: 'Patient', doctor_name: 'Doctor', current_workplace: 'Hospital / workplace', specialties: 'Specialties', languages: 'Languages',
  requested_changes: 'Requested change', schedule_date: 'Session date', session_date: 'Session date', start_time: 'Starts', end_time: 'Ends', serial_number: 'Serial',
  current_serial: 'Now serving', current_serial_running: 'Now serving', your_serial_number: 'Your serial', people_ahead: 'People ahead', delay_minutes: 'Delay (minutes)',
  maximum_patients: 'Session capacity', active_bookings: 'Existing bookings', appointment_status: 'Visit status', verification_status: 'Approval status',
  consultation_fee: 'Consultation fee', follow_up_fee: 'Follow-up fee', estimated_consultation_at: 'Estimated consultation', estimated_consultation_time: 'Estimated consultation',
  estimated_waiting_minutes: 'Estimated wait (minutes)', relationship_name: 'Relationship', is_active: 'Active', is_test: 'Sandbox payment',
  can_manage_schedules: 'Manage sessions', can_manage_appointments: 'Manage appointments', can_update_queue: 'Update queue', assistant_email: 'Assistant', target_email: 'Account',
  minimum_patient_age: 'Minimum age', maximum_patient_age: 'Maximum age', patient_age_range: 'Patient age range', confirmed_at: 'Availability confirmed',
  booking_open_at: 'Booking opens', booking_close_at: 'Booking closes', offer_expires_at: 'Reserved until', follow_up_date: 'Follow-up date', method: 'Payment method',
};
const hidden = new Set(['id', 'href', 'source_url', 'action', 'arguments', 'roster', 'existing_sessions', 'next_offset', 'timezone', 'error_code', 'updated_at', 'created_at', 'offered_at', 'generation_id', 'is_test']);
export const readableName = (value: string) => names[value] || fields[value] || value.replace(/^propose_/, '').replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
const titleCase = (value: string) => value.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
export function money(value: unknown, currency: unknown = 'BDT') {
  const amount = Number(value);
  const code = typeof currency === 'string' && /^[a-z]{3}$/i.test(currency) ? currency.toUpperCase() : 'BDT';
  return Number.isFinite(amount) ? new Intl.NumberFormat('en-BD', { style: 'currency', currency: code, currencyDisplay: 'code' }).format(amount) : String(value);
}
export function dateText(value: unknown) {
  if (typeof value !== 'string') return '';
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T00:00:00+06:00' : value);
  if (Number.isNaN(date.getTime())) return value;
  const options: Intl.DateTimeFormatOptions = { timeZone: 'Asia/Dhaka', day: 'numeric', month: 'short', year: 'numeric' };
  if (value.includes('T')) Object.assign(options, { hour: '2-digit', minute: '2-digit', hour12: false });
  return date.toLocaleString('en-GB', options);
}
function fieldText(key: string, value: unknown, currency: unknown): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (key === 'amount' || key.endsWith('_fee')) return money(value, currency);
  if (typeof value === 'string') {
    if (key === 'currency') return value.toUpperCase();
    if (/^\d{4}-\d{2}-\d{2}(T|$)/.test(value)) return dateText(value);
    if (/^\d{2}:\d{2}(:\d{2})?$/.test(value)) return value.slice(0, 5);
    if (key.includes('status') || key === 'method') return titleCase(value);
  }
  return String(value);
}
export function ChatLink({ href, onNavigate, children, className = '' }: { href: unknown; onNavigate?: () => void; children: React.ReactNode; className?: string }) {
  const safe = safeChatLink(href);
  if (!safe) return <span>{children}</span>;
  return safe.startsWith('/') ? <Link to={safe} onClick={onNavigate} className={className}>{children}</Link> : <a href={safe} className={className}>{children}</a>;
}
export function ChatText({ text, onNavigate }: { text: string; onNavigate?: () => void }) {
  return <div className="chat-prose"><Markdown skipHtml remarkPlugins={[remarkGfm]} allowedElements={['p', 'strong', 'em', 'del', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'a', 'br', 'code', 'pre', 'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr']} unwrapDisallowed={false} urlTransform={url => safeChatLink(url) || ''} components={{
    a: ({ href, children }) => <ChatLink href={href} onNavigate={onNavigate} className="font-semibold text-spandan-700 underline decoration-spandan-300 underline-offset-4">{children}</ChatLink>,
    h1: ({ children }) => <h3>{children}</h3>, h2: ({ children }) => <h3>{children}</h3>,
    table: ({ children }) => <div className="chat-table-scroll" tabIndex={0} role="region" aria-label="Response table"><table>{children}</table></div>,
  }}>{text}</Markdown></div>;
}
export function ChatDetails({ value, depth = 0, currency = 'BDT' }: { value: unknown; depth?: number; currency?: unknown }) {
  if (value == null || depth > 6) return null;
  if (typeof value !== 'object') return <span className="break-words [overflow-wrap:anywhere]">{typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}</span>;
  if (Array.isArray(value)) return <div className="space-y-3">{value.map((item, index) => <div key={index} className="min-w-0 rounded-xl border border-slate-100 bg-slate-50/60 p-3"><ChatDetails value={item} depth={depth + 1} currency={currency} /></div>)}</div>;
  const record = value as Record<string, unknown>;
  const entries = Object.entries(record).filter(([key, item]) => item != null && item !== '' && !hidden.has(key) && !key.endsWith('_id'));
  return <dl className="space-y-2.5 text-xs">{entries.map(([key, item]) => <div key={key} className={typeof item === 'object' ? 'min-w-0 space-y-2' : 'grid min-w-0 grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] items-start gap-3'}><dt className="font-medium text-slate-500">{readableName(key)}</dt><dd className="min-w-0 break-words font-medium text-slate-800 [overflow-wrap:anywhere]">{typeof item === 'object' ? <ChatDetails value={item} depth={depth + 1} currency={record.currency || currency} /> : fieldText(key, item, record.currency || currency)}</dd></div>)}</dl>;
}
export function StatusPill({ value }: { value: unknown }) {
  const status = String(value || '');
  const color = ['paid', 'succeeded', 'approved', 'completed', 'confirmed', 'open'].includes(status) ? 'border-spandan-200 bg-spandan-50 text-spandan-800' : ['pending', 'offered', 'waiting', 'in_consultation', 'refund_pending'].includes(status) ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-slate-200 bg-slate-100 text-slate-600';
  return <span className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${color}`}>{titleCase(status)}</span>;
}
function Fact({ icon: Icon, children }: { icon: typeof Clock3; children: React.ReactNode }) {
  return <p className="flex min-w-0 items-start gap-2 text-xs leading-relaxed text-slate-500"><Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" /><span className="min-w-0 break-words">{children}</span></p>;
}
function ItemBody({ item, tool, onNavigate }: { item: Record<string, any>; tool: string; onNavigate: () => void }) {
  if (tool === 'search_doctors' || tool === 'doctor_details') return <>
    <div className="flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-spandan-100 bg-spandan-50 font-bold text-spandan-700">{String(item.full_name || 'Dr').replace(/^Dr\.?\s*/i, '').charAt(0)}</span><div className="min-w-0"><h4 className="text-sm font-bold leading-snug text-slate-900">{item.full_name}</h4>{Array.isArray(item.specialties) && item.specialties.length > 0 && <p className="mt-1 text-xs font-medium text-spandan-700">{item.specialties.join(' · ')}</p>}</div></div>
    {item.current_workplace && <Fact icon={MapPin}>{item.current_workplace}</Fact>}
    {item.languages && <p className="text-xs text-slate-500">Languages: {item.languages}</p>}
    {(item.minimum_patient_age != null || item.maximum_patient_age != null) && <p className="text-xs text-slate-500">Patient ages: {item.minimum_patient_age ?? 0}{item.maximum_patient_age != null ? `–${item.maximum_patient_age} years` : '+ years'}</p>}
    {item.availability_note && <p className="rounded-xl bg-amber-50/80 p-3 text-xs leading-relaxed text-amber-900">{item.availability_note}</p>}
    <ChatLink href={item.href} onNavigate={onNavigate} className="chat-card-link">View doctor & sessions<ArrowUpRight className="h-3.5 w-3.5" /></ChatLink>
  </>;
  if (tool === 'list_appointments' || tool === 'appointment_details') {
    const session = item.session || {}; const chamber = session.chamber || {};
    return <><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-bold text-spandan-700">Serial #{item.serial_number}</span><StatusPill value={item.appointment_status} /></div><h4 className="text-sm font-bold text-slate-900">{item.doctor_name}</h4>{item.attendee_name && <p className="text-xs text-slate-600">Patient: {item.attendee_name}</p>}<Fact icon={CalendarDays}>{dateText(session.schedule_date)}{session.start_time && ` · ${session.start_time.slice(0, 5)}–${session.end_time?.slice(0, 5) || ''}`} · Dhaka time</Fact>{chamber.name && <Fact icon={MapPin}>{chamber.name}{chamber.area && `, ${chamber.area}`}</Fact>}{item.payment && <div className="flex flex-wrap justify-between gap-2 rounded-xl bg-slate-50 p-3 text-xs"><span className="text-slate-500">Consultation payment</span><span className="font-semibold">{money(item.payment.amount, item.payment.currency)} · {titleCase(item.payment.status)}</span></div>}<ChatLink href={item.href} onNavigate={onNavigate} className="chat-card-link">Open appointment<ArrowUpRight className="h-3.5 w-3.5" /></ChatLink></>;
  }
  if (['list_payments', 'payment_details', 'receipt'].includes(tool)) return <><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xl font-bold tracking-tight text-slate-900">{money(item.amount, item.currency)}</span><StatusPill value={item.status} /></div><h4 className="text-sm font-semibold">{item.doctor_name}</h4><Fact icon={CalendarDays}>{dateText(item.session_date)} · Serial #{item.serial_number}</Fact>{item.method && <p className="text-xs text-slate-500">Payment method: {titleCase(item.method)}</p>}<ChatLink href={item.href} onNavigate={onNavigate} className="chat-card-link">{tool === 'receipt' ? 'Open payment & receipt' : 'View payment options'}<ArrowUpRight className="h-3.5 w-3.5" /></ChatLink></>;
  if (tool === 'list_sessions') return <><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-bold">{dateText(item.schedule_date)}</h4><StatusPill value={item.status} /></div>{item.doctor_name && <p className="text-sm font-medium text-slate-800">{item.doctor_name}</p>}<Fact icon={Clock3}>{item.start_time?.slice(0, 5)}–{item.end_time?.slice(0, 5)} · Dhaka time</Fact>{item.chamber?.name && <Fact icon={MapPin}>{item.chamber.name}{item.chamber.district && `, ${item.chamber.district}`}</Fact>}{item.chamber?.consultation_fee != null && <p className="text-sm font-semibold text-spandan-800">{money(item.chamber.consultation_fee)} <span className="font-normal text-slate-500">consultation</span></p>}{item.availability_note && <p className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-500">{item.availability_note}</p>}{item.href && <ChatLink href={item.href} onNavigate={onNavigate} className="chat-card-link">Open session<ArrowUpRight className="h-3.5 w-3.5" /></ChatLink>}</>;
  if (tool === 'queue_status') return <><div className="grid grid-cols-2 gap-3">{[['Now serving', item.current_serial_running == null ? '—' : `#${item.current_serial_running}`], ['Your serial', item.your_serial_number == null ? '—' : `#${item.your_serial_number}`], ['People ahead', item.people_ahead ?? '—'], ['Delay', `${item.delay_minutes ?? 0} min`]].map(([name, value]) => <div key={name} className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] text-slate-500">{name}</p><p className="mt-1 text-lg font-bold text-slate-900">{value}</p></div>)}</div>{item.estimated_consultation_time && <Fact icon={Clock3}>Estimated consultation: {dateText(item.estimated_consultation_time)} · Dhaka time</Fact>}<p className="text-xs leading-relaxed text-slate-500">Queue times are estimates and may change as consultations progress.</p></>;
  if (tool === 'help') return <><h4 className="text-sm font-bold text-slate-900">{item.title}</h4><ChatText text={String(item.text || '')} onNavigate={onNavigate} /><ChatLink href={item.href} onNavigate={onNavigate} className="chat-card-link">Open in Spandan<ArrowUpRight className="h-3.5 w-3.5" /></ChatLink></>;
  return <><ChatDetails value={item} />{item.href && <ChatLink href={item.href} onNavigate={onNavigate} className="chat-card-link">Open in Spandan<ArrowUpRight className="h-3.5 w-3.5" /></ChatLink>}</>;
}
export function ChatResultCard({ card, ask, onNavigate }: { card: ToolCard; ask: (text: string) => void; onNavigate: () => void }) {
  const items = Array.isArray(card.data.items) ? card.data.items.filter(item => item && typeof item === 'object' && !Array.isArray(item)) : 'items' in card.data ? [] : [card.data];
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, 3);
  const Icon = ['search_doctors', 'doctor_details', 'list_specialties'].includes(card.tool) ? Stethoscope : ['list_payments', 'payment_details', 'receipt'].includes(card.tool) ? CreditCard : card.tool === 'help' ? FileText : card.tool === 'queue_status' ? Clock3 : CalendarDays;
  return <section className="chat-result-card" aria-label={readableName(card.tool)}><header className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/70 px-4 py-3"><h3 className="flex min-w-0 items-center gap-2 text-xs font-semibold text-slate-700"><Icon className="h-4 w-4 shrink-0 text-spandan-700" />{readableName(card.tool)}</h3><span className="inline-flex shrink-0 items-center gap-1 text-[10px] font-medium text-slate-500"><ShieldCheck className="h-3 w-3" />Spandan data</span></header><div className="divide-y divide-slate-100">{!items.length ? <div className="px-4 py-5"><Search className="mb-2 h-5 w-5 text-slate-400" /><p className="text-sm font-semibold">No matches this time</p><p className="mt-1 text-xs leading-relaxed text-slate-500">Try a different name, area, date, or specialty.</p></div> : visible.map((item, index) => <article key={String(item.id || index)} className="min-w-0 space-y-3 px-4 py-4"><ItemBody item={item} tool={card.tool} onNavigate={onNavigate} /></article>)}</div>{!expanded && items.length > 3 && <button type="button" className="flex min-h-11 w-full items-center justify-center border-t border-slate-100 text-xs font-semibold text-spandan-700 hover:bg-spandan-50" onClick={() => setExpanded(true)}>Show {items.length - 3} more in this reply</button>}{(expanded || items.length <= 3) && card.data.next_offset != null && <button type="button" onClick={() => ask(`Show the next page for ${readableName(card.tool).toLowerCase()}, using offset ${card.data.next_offset}. Keep my previous filters.`)} className="flex min-h-11 w-full items-center justify-center gap-2 border-t border-slate-100 text-xs font-semibold text-spandan-700 hover:bg-spandan-50">Show more results<ArrowUpRight className="h-3.5 w-3.5" /></button>}</section>;
}
