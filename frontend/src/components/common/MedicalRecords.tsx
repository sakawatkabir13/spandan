import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, FileText, ShieldCheck, Upload } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { PatientProfile } from '../../types';

export type Report = { id: string; title: string; report_type: string; report_date: string | null; notes: string; original_filename: string; content_type: string; size_bytes: number; created_at: string };
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

export function ReportList({ reports, download, remove, busy }: { reports: Report[]; download: (report: Report) => void; remove?: (report: Report) => void; busy: boolean }) {
  return <div className="space-y-3">{reports.length ? reports.map(report => <article key={report.id} className="rounded-2xl border border-slate-200 bg-white p-4 space-y-2">
    <div className="flex flex-wrap justify-between gap-3"><div className="min-w-0"><h3 className="font-semibold break-words flex items-center gap-2"><FileText className="h-4 w-4 shrink-0 text-spandan-600" />{report.title}</h3><p className="text-xs text-slate-500 mt-1 capitalize">{report.report_type} · {report.report_date ? dateLabel(report.report_date) : 'Date not provided'} · {(report.size_bytes / 1024 / 1024).toFixed(2)} MB</p></div>
      <div className="flex flex-wrap gap-3 text-sm"><button type="button" className="text-spandan-700 underline disabled:opacity-50" disabled={busy} onClick={() => download(report)}>Download report<span className="sr-only">: {report.title}</span></button>{remove && <button type="button" className="text-red-700 underline disabled:opacity-50" disabled={busy} onClick={() => remove(report)}>Remove<span className="sr-only">: {report.title}</span></button>}</div></div>
    {report.notes && <p className="text-sm text-slate-600 whitespace-pre-wrap break-words">{report.notes}</p>}
  </article>) : <p className="rounded-xl border border-dashed p-6 text-sm text-slate-500">No reports uploaded yet. If you have previous reports, add them before your visit. You can still book an appointment without them.</p>}</div>;
}

export function MedicalRecords({ profile }: { profile: PatientProfile }) {
  const [data, setData] = useState<MedicalData | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const load = async () => { const r = await apiClient.get('/medical-records/me'); setData(r.data.data); setHistory(r.data.data.history); };
  useEffect(() => { void load().catch(e => setError(errorMessage(e))); }, [profile.updated_at]);
  const perform = async (action: () => Promise<void>, success = '') => {
    setBusy(true); setError(''); setMessage('');
    try { await action(); if (success) setMessage(success); }
    catch (e) { setError(e instanceof Error && !('response' in e) ? e.message : errorMessage(e)); }
    finally { setBusy(false); }
  };
  if (!data || !history) return <section className="glass-card p-6" aria-label="Medical profile">{error ? <><p role="alert" className="text-red-700">{error}</p><button className="btn-secondary mt-3" onClick={() => void perform(load)}>Try again</button></> : <p role="status">Loading your medical profile…</p>}</section>;
  return <section className="glass-card p-6 space-y-6 scroll-mt-24" id="medical-records" aria-labelledby="medical-heading">
    <div className="flex flex-wrap justify-between items-start gap-3"><div><h2 id="medical-heading" className="text-xl font-bold">Medical profile & reports</h2><p className="text-sm text-slate-600 mt-1">Help your doctor prepare before you arrive.</p></div><span className="rounded-full bg-spandan-50 text-spandan-800 px-3 py-1 text-sm font-semibold">{data.completion.percent}% complete</span></div>
    <div className="h-2 rounded-full bg-slate-100" role="progressbar" aria-label="Profile completion" aria-valuenow={data.completion.percent} aria-valuemin={0} aria-valuemax={100}><div className="h-full rounded-full bg-spandan-500" style={{ width: `${data.completion.percent}%` }} /></div>
    <div className="flex flex-wrap gap-4 text-xs text-slate-600">{Object.entries(data.completion.steps).map(([name, done]) => <p key={name} className="flex items-center gap-1"><CheckCircle2 className={`h-4 w-4 ${done ? 'text-spandan-600' : 'text-slate-300'}`} />{name === 'personal_details' ? 'Date of birth, gender & emergency contact' : 'Medical history reviewed'}</p>)}</div>
    <p className="rounded-xl bg-blue-50 p-4 text-sm text-blue-950 flex gap-2"><ShieldCheck className="h-5 w-5 shrink-0" /><span>Your reports are private. If you enable sharing below, only the doctor for your appointment can access them, including 30 days of follow-up. Cancelled visits do not grant access. Staff and other patients cannot view them. Your records are not sent to the AI assistant.</span></p>
    {message && <p role="status" className="rounded-xl bg-spandan-50 p-3 text-spandan-800">{message}</p>}{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">{error}</p>}
    <form className="space-y-4" onSubmit={e => { e.preventDefault(); void perform(async () => { await apiClient.patch('/medical-records/me/history', Object.fromEntries(Object.entries(history).filter(([name]) => name !== 'updated_at'))); await load(); }, 'Medical history and sharing preferences saved.'); }}>
      <label className="block text-sm font-medium">Blood group<select aria-label="Blood group" className="input-field mt-1 max-w-xs" value={history.blood_group || ''} onChange={e => setHistory({ ...history, blood_group: e.target.value || null })}><option value="">Unknown / prefer not to say</option>{['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(group => <option key={group}>{group}</option>)}</select></label>
      {historyFields.map(([name, label, hint]) => <label key={name} className="block text-sm font-medium">{label}<textarea className="input-field mt-1" rows={2} maxLength={3000} value={history[name]} onChange={e => setHistory({ ...history, [name]: e.target.value })} placeholder={hint} /></label>)}
      <label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={history.history_reviewed} onChange={e => setHistory({ ...history, history_reviewed: e.target.checked })} /><span>I have reviewed my medical history, including if there is nothing to add.</span></label>
      <label className="flex items-start gap-3 rounded-xl border border-spandan-200 bg-spandan-50 p-4 text-sm"><input type="checkbox" className="mt-1" checked={history.share_with_doctors} onChange={e => setHistory({ ...history, share_with_doctors: e.target.checked })} /><span>Share my medical history and reports with the doctors I book. I can turn this off at any time. Account-holder reports are not shared for family-member appointments.</span></label>
      <button disabled={busy} className="btn-primary">{busy ? 'Saving…' : 'Save medical history'}</button>
    </form>
    <div className="border-t pt-6 space-y-4"><div><h3 className="text-lg font-bold">Medical reports</h3><p className="text-xs text-slate-500 mt-1">PDF, JPEG, PNG, or WebP · 5 MB per file · {data.reports.length}/{data.limits.max_reports} reports · {(data.limits.used_bytes / 1024 / 1024).toFixed(1)} MB of 100 MB used</p></div>
      <form className="rounded-2xl bg-slate-50 p-4 space-y-3" onSubmit={e => { e.preventDefault(); const form = e.currentTarget; if (!file) { setError('Choose a report file first.'); return; } if (file.size > data.limits.max_file_bytes) { setError('Reports must be 5 MB or smaller.'); return; } const body = new FormData(form); if (!body.get('report_date')) body.delete('report_date'); void perform(async () => { await apiClient.post('/medical-records/me/reports', body, { headers: { 'Content-Type': 'multipart/form-data' } }); form.reset(); setFile(null); await load(); }, 'Medical report uploaded securely.'); }}>
        <label className="block text-sm">Report title<input name="title" className="input-field mt-1" required minLength={2} maxLength={120} placeholder="For example, complete blood count" /></label>
        <div className="grid sm:grid-cols-2 gap-3"><label className="block text-sm">Report category<select aria-label="Report category" name="report_type" className="input-field mt-1"><option value="lab">Lab result</option><option value="imaging">Imaging / scan</option><option value="prescription">Prescription</option><option value="discharge">Discharge summary</option><option value="other">Other</option></select></label><label className="block text-sm">Report date (optional)<input name="report_date" type="date" className="input-field mt-1" max={new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dhaka' })} /></label></div>
        <label className="block text-sm">Notes for your doctor (optional)<textarea name="notes" rows={2} maxLength={1000} className="input-field mt-1" /></label>
        <label className="block text-sm">Report file<input ref={input} name="file" type="file" required accept="application/pdf,image/jpeg,image/png,image/webp" className="mt-2 block w-full text-sm" onChange={e => setFile(e.target.files?.[0] || null)} /></label>
        <button disabled={busy || !file} className="btn-secondary"><Upload className="h-4 w-4" />{busy ? 'Uploading…' : 'Upload report'}</button>
      </form>
      <ReportList reports={data.reports} busy={busy} download={report => void perform(() => downloadMedicalReport(`/medical-records/me/reports/${report.id}/download`, report.original_filename))} remove={report => { if (window.confirm(`Remove “${report.title}”? Your booked doctors will no longer be able to download it.`)) void perform(async () => { await apiClient.delete(`/medical-records/me/reports/${report.id}`); await load(); }, 'Report removed.'); }} />
    </div>
    <Link to="/dashboard/patient" className="inline-block text-sm underline text-spandan-700">Continue to my appointments</Link>
  </section>;
}

export function MedicalSummary({ history }: { history: History }) {
  return <dl className="grid sm:grid-cols-2 gap-4"><div className="rounded-xl border p-4"><dt className="text-sm text-slate-500">Blood group</dt><dd className="font-semibold">{history.blood_group || 'Not provided'}</dd></div>{historyFields.map(([name, label]) => <div key={name} className="rounded-xl border p-4"><dt className="text-sm text-slate-500">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm">{history[name] || 'Not provided'}</dd></div>)}</dl>;
}
