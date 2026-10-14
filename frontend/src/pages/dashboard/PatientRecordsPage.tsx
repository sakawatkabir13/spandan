import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { MedicalData, MedicalSummary, ReportList, downloadMedicalReport, Report } from '../../components/common/MedicalRecords';

type PatientRecords = Partial<MedicalData> & { shared: boolean; dependent_booking: boolean; patient: { full_name: string; date_of_birth?: string; gender?: string; emergency_contact?: string } };
export function PatientRecordsPage() {
  const { appointmentId } = useParams();
  const [data, setData] = useState<PatientRecords | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = async () => { setError(''); try { setData((await apiClient.get(`/medical-records/appointments/${appointmentId}`)).data.data); } catch (e) { setError(errorMessage(e)); } };
  useEffect(() => { void load(); }, [appointmentId]);
  const download = async (report: Report) => { setBusy(true); setError(''); try { await downloadMedicalReport(`/medical-records/appointments/${appointmentId}/reports/${report.id}/download`, report.original_filename); } catch (e) { setError(e instanceof Error ? e.message : errorMessage(e)); } finally { setBusy(false); } };
  return <DashboardLayout><div className="space-y-6">
    <Link to="/dashboard/doctor/queue" className="text-sm text-spandan-700 underline">Back to patient queue</Link>
    <section className="glass-card p-6 space-y-4"><div className="flex flex-wrap justify-between gap-3"><div><h1 className="text-2xl font-bold">Patient medical records</h1>{data && <p className="text-slate-600 mt-1">{data.patient.full_name}</p>}</div><button className="btn-secondary" disabled={busy} onClick={() => void load()}>Refresh records</button></div>
      {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error}</p>}
      {!data && !error && <p role="status">Loading patient records…</p>}
      {data && !data.shared && <p className="rounded-xl bg-slate-50 p-4 text-slate-600">{data.dependent_booking ? 'This appointment is for a family member. The account holder’s medical records are not shared for this visit. Ask the patient to bring the family member’s reports.' : 'The patient has not enabled medical-record sharing. Ask them to update the sharing preference in their medical profile before the visit.'}</p>}
      {data?.shared && <><div className="grid sm:grid-cols-3 gap-3 text-sm"><p>Date of birth: {data.patient.date_of_birth || 'Not provided'}</p><p>Gender: {data.patient.gender || 'Not provided'}</p><p>Emergency contact: {data.patient.emergency_contact || 'Not provided'}</p></div><p className="rounded-xl bg-blue-50 p-3 text-sm text-blue-950">Patient-provided history. Confirm details during the consultation. Access is recorded and ends when sharing is disabled or the appointment access period expires.</p>{data.history && <MedicalSummary history={data.history} />}<h2 className="text-lg font-bold">Reports ({data.reports?.length || 0})</h2><ReportList reports={data.reports || []} busy={busy} download={report => void download(report)} /></>}
    </section>
  </div></DashboardLayout>;
}
