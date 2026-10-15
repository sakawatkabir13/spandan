import { I18nText } from '../../context/LanguageContext';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FileHeart } from 'lucide-react';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { MedicalRecords } from '../../components/common/MedicalRecords';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { PatientProfile } from '../../types';

export function HealthRecordsPage() {
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [family, setFamily] = useState<{ id: string; full_name: string; is_active: boolean }[]>([]);
  const [params, setParams] = useSearchParams();
  const dependent = params.get('dependent_id') || '';
  const [error, setError] = useState('');
  const [dirty, setDirty] = useState(false);
  useEffect(() => { void Promise.all([apiClient.get('/patients/me'), apiClient.get('/dependents?include_archived=true')]).then(([p, f]) => { setProfile(p.data.data); setFamily(f.data.data); }).catch(e => setError(errorMessage(e))); }, []);
  return <DashboardLayout><div className="space-y-6"><header><h1 className="page-heading"> <I18nText text={"Health records"} /> </h1><p className="page-description"> <I18nText text={"Prepare for your visit with the right history and reports for each family member."} /> </p></header><div className="flex flex-wrap items-end justify-between gap-4"><label className="block w-full text-sm font-medium sm:max-w-sm"> <I18nText text={"Whose records?"} /> <select className="input-field mt-2" value={dependent} onChange={e => { if (dirty && !window.confirm('Discard unsaved changes before switching to another family chart?')) return; setDirty(false); setParams(e.target.value ? { dependent_id: e.target.value } : {}); }}><option value="">{profile?.full_name || 'My records'}  <I18nText text={"(myself)"} /> </option>{family.map(person => <option key={person.id} value={person.id}>{person.full_name}{!person.is_active ? ' (archived)' : ''}</option>)}</select></label><Link to="/dashboard/patient/tools?tab=family" className="btn-secondary text-sm"> <I18nText text={"Manage family members"} /> </Link></div>{error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error}</p>}{profile ? <MedicalRecords key={dependent} profile={profile} dependentId={dependent} onDirtyChange={setDirty} /> : !error && <div className="glass-card flex items-center gap-3 p-6" role="status"><FileHeart className="h-5 w-5 text-spandan-600" /> <I18nText text={"Loading your private chart…"} /> </div>}</div></DashboardLayout>;
}
