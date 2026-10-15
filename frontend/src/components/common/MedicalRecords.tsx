import { I18nText } from '../../context/LanguageContext';
import { useLanguage } from '../../context/LanguageContext';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Eye, FileText, ShieldCheck, Upload } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { PatientProfile } from '../../types';
import { Modal } from './Modal';
const PdfReportPreview = lazy(() => import('./PdfReportPreview'));

export type Report = { id: string; title: string; report_type: string; report_date: string | null; notes: string; original_filename: string; content_type: string; size_bytes: number; created_at: string; share_with_doctors?: boolean; dependent_id?: string | null };
export type History = { blood_group: string | null; allergies: string; medications: string; conditions: string; surgeries: string; family_history: string; history_reviewed: boolean; share_with_doctors: boolean; updated_at?: string };
export type MedicalData = { history: History; reports: Report[]; completion: { percent: number; steps: Record<string, boolean> }; limits: { used_bytes: number; max_total_bytes: number; max_reports: number; max_file_bytes: number } };
const historyFields = [['allergies', 'Allergies', 'Include medicine and food allergies, or write “None known”.'], ['medications', 'Current medicines', 'Include names, doses, and how often you take them.'], ['conditions', 'Long-term conditions', 'For example, diabetes, asthma, or high blood pressure.'], ['surgeries', 'Previous operations or hospital stays', 'Include the year if you remember it.'], ['family_history', 'Relevant family history', 'Conditions in close relatives that your doctor should know about.']] as const;
const dateLabel = (value: string) => new Date(value.length === 10 ? value + 'T00:00:00' : value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

export async function downloadMedicalReport(path: string, filename: string) {
  try {
    const response = await apiClient.get(path, { responseType: 'blob' });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error: any) {
    if (error.response?.data instanceof Blob) {
      try { const data = JSON.parse(await error.response.data.text()); throw new Error(data.error?.message || 'Unable to download this report.'); }
      catch (parsed) { if (parsed instanceof SyntaxError) throw new Error('Unable to download this report.'); throw parsed; }
    }
    throw error;
  }
}

export function ReportList({ reports, download, remove, preview, sharing, busy }: { reports: Report[]; download: (report: Report) => void; remove?: (report: Report) => void; preview?: (report: Report) => void; sharing?: (report: Report) => void; busy: boolean }) {
  return <div className="space-y-3">{reports.length ? reports.map((report, index) => <div key={report.id}>{(index === 0 || reports[index - 1].report_date?.slice(0, 7) !== report.report_date?.slice(0, 7)) && <h3 className="mb-3 mt-5 text-sm font-semibold text-slate-500">{report.report_date ? new Date(report.report_date.slice(0, 7) + '-01T00:00:00').toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }) : 'Undated reports'}</h3>}<article className="rounded-2xl border border-slate-200 bg-white p-4 space-y-2">
    <div className="flex flex-wrap justify-between gap-3"><div className="min-w-0"><h3 className="font-semibold break-words flex items-start gap-2"><FileText className="h-4 w-4 shrink-0 text-spandan-600" /><span className="min-w-0">{report.title}</span></h3><p className="text-xs text-slate-500 mt-1 capitalize">{report.report_type} · {report.report_date ? dateLabel(report.report_date) : 'Date not provided'} · {(report.size_bytes / 1024 / 1024).toFixed(2)}  <I18nText text={"MB"} /> </p></div>
      <div className="flex flex-wrap gap-2 text-sm">{preview && <button type="button" className="btn-secondary text-sm" disabled={busy} onClick={() => preview(report)}><Eye className="h-4 w-4" /> <I18nText text={"Preview"} /> <span className="sr-only">: {report.title}</span></button>}<button type="button" className="btn-secondary text-sm disabled:opacity-50" disabled={busy} onClick={() => download(report)}> <I18nText text={"Download report"} /> <span className="sr-only">: {report.title}</span></button>{remove && <button type="button" className="min-h-11 px-3 text-red-700 disabled:opacity-50" disabled={busy} onClick={() => remove(report)}> <I18nText text={"Remove"} /> <span className="sr-only">: {report.title}</span></button>}</div></div>
    {report.notes && <p className="text-sm text-slate-600 whitespace-pre-wrap break-words">{report.notes}</p>}
    {sharing && <label className="flex items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-600"><input type="checkbox" disabled={busy} checked={report.share_with_doctors !== false} onChange={() => sharing(report)} /> <I18nText text={"Allow this report to be shared with my booked doctor"} /> </label>}
  </article></div>) : <p className="rounded-xl border border-dashed p-6 text-sm text-slate-500"> <I18nText text={"No reports uploaded yet. If you have previous reports, add them before your visit. You can still book an appointment without them."} /> </p>}</div>;
}

export function MedicalRecords({ profile, dependentId = '', onDirtyChange }: { profile: PatientProfile; dependentId?: string; onDirtyChange?: (dirty: boolean) => void }) {
  const { t: uiText } = useLanguage();
  const [data, setData] = useState<MedicalData | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dirty, setDirty] = useState(false);
  const [uploadDirty, setUploadDirty] = useState(false);
  useEffect(() => { onDirtyChange?.(dirty || uploadDirty); }, [dirty, uploadDirty, onDirtyChange]);
  useEffect(() => { const guard = (event: BeforeUnloadEvent) => { if (dirty || uploadDirty) { event.preventDefault(); event.returnValue = ''; } }; window.addEventListener('beforeunload', guard); return () => window.removeEventListener('beforeunload', guard); }, [dirty, uploadDirty]);
  const [tab, setTab] = useState('history');
  const [category, setCategory] = useState('all');
  const preview = useReportPreview();
  const suffix = dependentId ? `?dependent_id=${encodeURIComponent(dependentId)}` : '';
  const input = useRef<HTMLInputElement>(null);
  const load = async (replaceHistory = false) => { const r = await apiClient.get(`/medical-records/me${suffix}`); setData(r.data.data); setHistory(previous => !replaceHistory && dirty && previous ? previous : r.data.data.history); if (replaceHistory) setDirty(false); };
  useEffect(() => { void load().catch(e => setError(errorMessage(e))); }, [profile.updated_at]);
  const perform = async (action: () => Promise<void>, success = '') => {
    setBusy(true); setError(''); setMessage('');
    try { await action(); if (success) setMessage(success); }
    catch (e) { setError(e instanceof Error && !('response' in e) ? e.message : errorMessage(e)); }
    finally { setBusy(false); }
  };
  if (!data || !history) return <section className="glass-card p-6" aria-label={uiText("Medical profile")}>{error ? <><p role="alert" className="text-red-700">{error}</p><button className="btn-secondary mt-3" onClick={() => void perform(load)}> <I18nText text={"Try again"} /> </button></> : <p role="status"> <I18nText text={"Loading your medical profile…"} /> </p>}</section>;
  return <section className="glass-card p-6 space-y-6 scroll-mt-24" id="medical-records" aria-labelledby="medical-heading">
    <div className="flex flex-wrap justify-between items-start gap-3"><div><h2 id="medical-heading" className="text-xl font-bold"> <I18nText text={"Medical profile & reports"} /> </h2><p className="text-sm text-slate-600 mt-1"> <I18nText text={"Help your doctor prepare before you arrive."} /> </p></div><span className="rounded-full bg-spandan-50 text-spandan-800 px-3 py-1 text-sm font-semibold">{data.completion.percent} <I18nText text={"% complete"} /> </span></div>
    <div className="h-2 rounded-full bg-slate-100" role="progressbar" aria-label={uiText("Profile completion")} aria-valuenow={data.completion.percent} aria-valuemin={0} aria-valuemax={100}><div className="h-full rounded-full bg-spandan-500" style={{ width: `${data.completion.percent}%` }} /></div>
    <div className="flex flex-wrap gap-4 text-xs text-slate-600">{Object.entries(data.completion.steps).map(([name, done]) => <p key={name} className="flex items-center gap-1"><CheckCircle2 className={`h-4 w-4 ${done ? 'text-spandan-600' : 'text-slate-300'}`} />{name === 'personal_details' ? 'Date of birth, gender & emergency contact' : 'Medical history reviewed'}</p>)}</div>
    <p className="rounded-xl bg-blue-50 p-4 text-sm text-blue-950 flex gap-2"><ShieldCheck className="h-5 w-5 shrink-0" /><span> <I18nText text={"Your reports are private. If you enable sharing below, only the doctor for your appointment can access them, including 30 days of follow-up. Cancelled visits do not grant access. Staff and other patients cannot view them. Your records are not sent to the AI assistant."} /> </span></p>
    {message && <p role="status" className="rounded-xl bg-spandan-50 p-3 text-spandan-800">{message}</p>}{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">{error}</p>}
    <nav aria-label={uiText("Medical profile sections")} className="segmented-control">{[['history', 'Medical history'], ['reports', 'Reports & timeline'], ['access', 'Doctor access']].map(([value, label]) => <button key={value} type="button" aria-pressed={tab === value} onClick={() => setTab(value)}><I18nText text={label} /></button>)}</nav>
    <form hidden={tab !== 'history'} onChange={() => setDirty(true)} className="space-y-4" onSubmit={e => { e.preventDefault(); void perform(async () => { await apiClient.patch(`/medical-records/me/history${suffix}`, Object.fromEntries(Object.entries(history).filter(([name]) => name !== 'updated_at'))); await load(true); }, 'Medical history and sharing preferences saved.'); }}>
      <label className="block text-sm font-medium"> <I18nText text={"Blood group"} /> <select aria-label={uiText("Blood group")} className="input-field mt-1 max-w-xs" value={history.blood_group || ''} onChange={e => setHistory({ ...history, blood_group: e.target.value || null })}><option value=""> <I18nText text={"Unknown / prefer not to say"} /> </option>{['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(group => <option key={group}>{group}</option>)}</select></label>
      <div className="grid sm:grid-cols-2 gap-4">{historyFields.map(([name, label, hint]) => <label key={name} className="block text-sm font-medium"><I18nText text={label} /><textarea className="input-field mt-1" rows={2} maxLength={3000} value={history[name]} onChange={e => setHistory({ ...history, [name]: e.target.value })} placeholder={uiText(hint)} /></label>)}</div>
      <label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={history.history_reviewed} onChange={e => setHistory({ ...history, history_reviewed: e.target.checked })} /><span> <I18nText text={"I have reviewed my medical history, including if there is nothing to add."} /> </span></label>
      <label className="flex items-start gap-3 rounded-xl border border-spandan-200 bg-spandan-50 p-4 text-sm"><input type="checkbox" className="mt-1" checked={history.share_with_doctors} onChange={e => setHistory({ ...history, share_with_doctors: e.target.checked })} /><span> <I18nText text={"Share this person's history and shareable reports with their booked doctors by default. Choose different reports for each visit from its details page. Family members have separate charts."} /> </span></label>
      <button disabled={busy} className="btn-primary">{busy ? 'Saving…' : 'Save medical history'}</button>
    </form>
    <div hidden={tab !== 'reports'} className="space-y-4"><div><h3 className="text-lg font-bold"> <I18nText text={"Medical reports"} /> </h3><p className="text-xs text-slate-500 mt-1"> <I18nText text={"PDF, JPEG, PNG, or WebP · 5 MB per file · Reports are optional for profile completion."} /> </p></div>
      <details className="rounded-xl border border-slate-200 p-4"><summary className="text-sm font-semibold text-spandan-700"> <I18nText text={"Add a medical report"} /> </summary><form onChange={() => setUploadDirty(true)} className="mt-4 space-y-3" onSubmit={e => { e.preventDefault(); const form = e.currentTarget; if (!file) { setError('Choose a report file first.'); return; } if (file.size > data.limits.max_file_bytes) { setError('Reports must be 5 MB or smaller.'); return; } const body = new FormData(form); if (!body.get('report_date')) body.delete('report_date'); void perform(async () => { await apiClient.post(`/medical-records/me/reports${suffix}`, body, { headers: { 'Content-Type': 'multipart/form-data' } }); form.reset(); setFile(null); setUploadDirty(false); await load(); }, 'Medical report uploaded securely.'); }}>
        <label className="block text-sm"> <I18nText text={"Report title"} /> <input name="title" className="input-field mt-1" required minLength={2} maxLength={120} placeholder={uiText("For example, complete blood count")} /></label>
        <div className="grid sm:grid-cols-2 gap-3"><label className="block text-sm"> <I18nText text={"Report category"} /> <select aria-label={uiText("Report category")} name="report_type" className="input-field mt-1"><option value="lab"> <I18nText text={"Lab result"} /> </option><option value="imaging"> <I18nText text={"Imaging / scan"} /> </option><option value="prescription"> <I18nText text={"Prescription"} /> </option><option value="discharge"> <I18nText text={"Discharge summary"} /> </option><option value="other"> <I18nText text={"Other"} /> </option></select></label><label className="block text-sm"> <I18nText text={"Report date (optional)"} /> <input name="report_date" type="date" className="input-field mt-1" max={new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dhaka' })} /></label></div>
        <label className="block text-sm"> <I18nText text={"Notes for your doctor (optional)"} /> <textarea name="notes" rows={2} maxLength={1000} className="input-field mt-1" /></label>
        <label className="block text-sm"> <I18nText text={"Report file"} /> <input ref={input} name="file" type="file" required accept="application/pdf,image/jpeg,image/png,image/webp" className="mt-2 block w-full rounded-xl border border-slate-200 bg-white p-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-spandan-50 file:px-3 file:py-2 file:font-medium file:text-spandan-800" onChange={e => setFile(e.target.files?.[0] || null)} /></label>
        <button disabled={busy || !file} className="btn-secondary"><Upload className="h-4 w-4" />{busy ? 'Uploading…' : 'Upload report'}</button>
      </form></details>
      <label className="block text-sm font-medium"> <I18nText text={"Filter report category"} /> <select className="input-field mt-1 max-w-xs" value={category} onChange={e => setCategory(e.target.value)}><option value="all"> <I18nText text={"All categories"} /> </option>{['lab', 'imaging', 'prescription', 'discharge', 'other'].map(value => <option key={value}>{value}</option>)}</select></label>
      <ReportList reports={data.reports.filter(r => category === 'all' || r.report_type === category)} busy={busy} preview={report => void perform(() => preview.open(report, `/medical-records/me/reports/${report.id}/preview`))} sharing={report => void perform(async () => { await apiClient.patch(`/medical-records/me/reports/${report.id}/sharing?shared=${report.share_with_doctors === false}`); await load(); }, 'Report sharing saved.')} download={report => void perform(() => downloadMedicalReport(`/medical-records/me/reports/${report.id}/download`, report.original_filename))} remove={report => { if (window.confirm(`Remove “${report.title}”? Your booked doctors will no longer be able to download it.`)) void perform(async () => { await apiClient.delete(`/medical-records/me/reports/${report.id}`); await load(); }, 'Report removed.'); }} />
    </div>
    {tab === 'access' && <DoctorAccessHistory />}
    {preview.dialog}
    <Link to="/dashboard/patient" className="inline-block text-sm underline text-spandan-700"> <I18nText text={"Continue to my appointments"} /> </Link>
  </section>;
}

export function useReportPreview() {
  const [value, setValue] = useState<{ url: string; report: Report; bytes: Uint8Array } | null>(null);
  const currentUrl = useRef<string | null>(null);
  const request = useRef(0);
  useEffect(() => () => { request.current++; if (currentUrl.current) URL.revokeObjectURL(currentUrl.current); }, []);
  const close = () => { request.current++; if (currentUrl.current) URL.revokeObjectURL(currentUrl.current); currentUrl.current = null; setValue(null); };
  const open = async (report: Report, path: string) => {
    close();
    const sequence = request.current;
    const response = await apiClient.get(path, { responseType: 'blob' });
    const bytes = new Uint8Array(await (response.data as Blob).arrayBuffer());
    if (sequence !== request.current) return;
    const url = URL.createObjectURL(new Blob([response.data], { type: report.content_type }));
    currentUrl.current = url; setValue({ url, report, bytes });
  };
  return { open, dialog: <Modal isOpen={!!value} onClose={close} title={value?.report.title || 'Report preview'} maxWidth="2xl">{value && <><p className="mb-3 text-xs text-slate-500"> <I18nText text={"Private preview. Close this window when finished."} /> </p>{value.report.content_type === 'application/pdf' ? <Suspense fallback={<p role="status"><I18nText text="Loading PDF preview…" /></p>}><PdfReportPreview data={value.bytes} /></Suspense> : <img src={value.url} alt={value.report.title} className="mx-auto max-h-[65dvh] max-w-full object-contain" />}</>}</Modal> };
}

function DoctorAccessHistory() {
  const [rows, setRows] = useState<{ id: string; doctor_name: string; action: string; created_at: string }[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { void apiClient.get('/medical-records/access-history').then(r => setRows(r.data.data)).catch(e => setError(errorMessage(e))); }, []);
  return <section className="space-y-3"><h3 className="section-heading"> <I18nText text={"Who accessed your records"} /> </h3><p className="text-sm text-slate-500"> <I18nText text={"Recent access by your booked doctors, across your family's charts."} /> </p>{error && <p role="alert">{error}</p>}{rows === null && !error ? <p role="status"> <I18nText text={"Loading access history…"} /> </p> : !rows?.length ? <p className="empty-state text-sm"> <I18nText text={"No doctor access recorded yet."} /> </p> : <ol className="divide-y divide-slate-100">{rows.map(row => <li key={row.id} className="flex flex-wrap justify-between gap-2 py-3 text-sm"><div><p className="font-semibold">{row.doctor_name}</p><p className="text-slate-500">{row.action === 'medical.records_viewed' ? 'Viewed a shared chart' : row.action === 'medical.report_previewed' ? 'Previewed a shared report' : 'Downloaded a shared report'}</p></div><time className="text-xs text-slate-500" dateTime={row.created_at}>{new Date(row.created_at).toLocaleString('en-GB', { timeZone: 'Asia/Dhaka' })}</time></li>)}</ol>}</section>;
}

export function MedicalSummary({ history }: { history: History }) {
  return <dl className="grid sm:grid-cols-2 gap-4"><div className="rounded-xl border p-4"><dt className="text-sm text-slate-500"> <I18nText text={"Blood group"} /> </dt><dd className="font-semibold">{history.blood_group || 'Not provided'}</dd></div>{historyFields.map(([name, label]) => <div key={name} className="rounded-xl border p-4"><dt className="text-sm text-slate-500"><I18nText text={label} /></dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm">{history[name] || 'Not provided'}</dd></div>)}</dl>;
}
