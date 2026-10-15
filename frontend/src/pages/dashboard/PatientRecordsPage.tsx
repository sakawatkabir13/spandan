import { I18nText } from '../../context/LanguageContext';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { MedicalData, MedicalSummary, ReportList, downloadMedicalReport, Report, useReportPreview } from '../../components/common/MedicalRecords';
import { VisitSummary } from '../../components/common/VisitSummary';

type PatientRecords = Partial<MedicalData> & { shared: boolean; history_shared?: boolean; dependent_booking: boolean; patient: { full_name: string; date_of_birth?: string; gender?: string; emergency_contact?: string } };
export function PatientRecordsPage() {
  const { appointmentId } = useParams();
  const [data, setData] = useState<PatientRecords | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const preview = useReportPreview();
  const load = async () => { setError(''); try { setData((await apiClient.get(`/medical-records/appointments/${appointmentId}`)).data.data); } catch (e) { setError(errorMessage(e)); } };
  useEffect(() => { void load(); void apiClient.get(`/appointments/${appointmentId}`).then(r => setStatus(r.data.data.appointment_status)).catch(e => setError(errorMessage(e))); }, [appointmentId]);
  const download = async (report: Report) => { setBusy(true); setError(''); try { await downloadMedicalReport(`/medical-records/appointments/${appointmentId}/reports/${report.id}/download`, report.original_filename); } catch (e) { setError(e instanceof Error ? e.message : errorMessage(e)); } finally { setBusy(false); } };
  return <DashboardLayout><div className="space-y-6">
    <Link to="/dashboard/doctor/queue" className="text-sm text-spandan-700 underline"> <I18nText text={"Back to patient queue"} /> </Link>
    <div className="grid items-start gap-5 xl:grid-cols-2">
    <section className="glass-card p-6 space-y-4"><div className="flex flex-wrap justify-between gap-3"><div><h1 className="text-2xl font-bold"> <I18nText text={"Patient medical records"} /> </h1>{data && <p className="text-slate-600 mt-1">{data.patient.full_name}</p>}</div><button className="btn-secondary" disabled={busy} onClick={() => void load()}> <I18nText text={"Refresh records"} /> </button></div>
      {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error}</p>}
      {!data && !error && <p role="status"> <I18nText text={"Loading patient records…"} /> </p>}
      {data && !data.shared && <p className="rounded-xl bg-slate-50 p-4 text-slate-600"> <I18nText text={"The patient has not shared this person's records for the visit. They can choose history and reports from their appointment details page."} /> </p>}
      {data?.shared && <><div className="grid sm:grid-cols-3 gap-3 text-sm"><p> <I18nText text={"Date of birth:"} /> {data.patient.date_of_birth || 'Not provided'}</p><p> <I18nText text={"Gender:"} /> {data.patient.gender || 'Not provided'}</p><p> <I18nText text={"Emergency contact:"} /> {data.patient.emergency_contact || 'Not provided'}</p></div><p className="rounded-xl bg-blue-50 p-3 text-sm text-blue-950"> <I18nText text={"Patient-provided history. Confirm details during the consultation. Access is recorded and ends when sharing is disabled or the appointment access period expires."} /> </p>{data.history && data.history_shared !== false && <MedicalSummary history={data.history} />}<h2 className="text-lg font-bold"> <I18nText text={"Reports ("} /> {data.reports?.length || 0})</h2><ReportList reports={data.reports || []} busy={busy} preview={report => { setBusy(true); void preview.open(report, `/medical-records/appointments/${appointmentId}/reports/${report.id}/preview`).catch(e => setError(errorMessage(e))).finally(() => setBusy(false)); }} download={report => void download(report)} /></>}
    </section>
    {appointmentId && <VisitSummary appointmentId={appointmentId} editable canWrite={['in_consultation', 'completed'].includes(status)} />}
    </div>{preview.dialog}
  </div></DashboardLayout>;
}
