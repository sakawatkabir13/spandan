import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, CalendarDays, ChevronRight, FileHeart, Search, ShieldCheck, Sparkles, Stethoscope } from 'lucide-react';
import { apiClient } from '../api/client';
import { ApiResponse, Specialization } from '../types';
import { MainLayout } from '../components/layout/MainLayout';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';

export const Home = () => {
  const { t: uiText } = useLanguage();
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [query, setQuery] = useState('');
  const [specialty, setSpecialty] = useState('');
  const { t } = useLanguage();
  const { user } = useAuth();
  const navigate = useNavigate();
  useEffect(() => { void apiClient.get<ApiResponse<Specialization[]>>('/doctors/specializations').then(r => setSpecializations(r.data.data)).catch(() => {}); }, []);
  const search = (event: React.FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams({ view: 'booking' });
    if (query.trim()) params.set('query', query.trim());
    if (specialty) params.set('specialization_id', specialty);
    navigate(`/doctors?${params}`);
  };
  return <MainLayout>
    <section className="grid items-center gap-8 py-5 sm:py-10 lg:grid-cols-[1.2fr_1fr] lg:gap-14 lg:py-14">
      <div className="max-w-2xl">
        <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-spandan-200 bg-spandan-50 px-3 py-1.5 text-sm text-spandan-800"><span className="h-2 w-2 rounded-full bg-spandan-500" />{t('Private chamber appointments, made easier')}</p>
        <h1 className="max-w-xl text-[2.65rem] font-bold leading-[1.08] tracking-[-.045em] text-spandan-950 sm:text-6xl lg:text-[4.25rem]">{t('A clearer path to your next doctor visit.')}</h1>
        <p className="mt-6 max-w-lg text-base leading-relaxed text-slate-600 sm:text-lg">{t('Find a specialist, book your serial, and follow the queue. Keep your visit details and health records together with Spandan.')}</p>
        <div className="mt-7 flex flex-wrap gap-3"><Link to="/doctors?view=booking" className="btn-primary">{t('Find a doctor')}<ArrowRight className="h-4 w-4" /></Link><Link to={user?.role === 'patient' ? '/dashboard/patient' : '/login'} className="btn-secondary">{t('Manage my visits')}</Link></div>
        <p className="mt-5 flex items-center gap-2 text-xs text-slate-500"><ShieldCheck className="h-4 w-4 text-spandan-600" />{t('Your records stay private. You decide what to share.')}</p>
      </div>
      <div className="relative overflow-hidden rounded-[1.75rem] border border-spandan-200 bg-spandan-100/50 p-5 sm:p-8">
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full border-[32px] border-spandan-200/50" aria-hidden="true" />
        <div className="relative rounded-2xl border border-white bg-white p-5 shadow-glass sm:p-7">
          <div className="flex items-center justify-between border-b border-slate-100 pb-5"><div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-spandan-50 text-spandan-700"><CalendarDays className="h-6 w-6" /></span><div><h2 className="font-semibold text-spandan-950">{t('Your visit, from start to finish')}</h2><p className="text-xs text-slate-500">{t('One place to stay prepared')}</p></div></div></div>
          <ol className="mt-5 space-y-6">{[
            { title: 'Find the right specialist', text: 'Compare specialties, chambers, fees, and available sessions.' },
            { title: 'Book and prepare', text: 'Reserve your serial and choose the reports to share.' },
            { title: 'Follow your queue', text: 'Check progress before travelling. Arrival times are estimates.' },
          ].map((step, i) => <li key={step.title} className="flex gap-4"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-spandan-50 text-sm font-semibold text-spandan-700">{i + 1}</div><div><h3 className="text-sm font-semibold text-slate-900">{t(step.title)}</h3><p className="mt-1 text-sm leading-relaxed text-slate-500">{t(step.text)}</p></div></li>)}</ol>
          <Link to="/ai-triage" className="mt-6 flex items-center gap-3 rounded-xl bg-spandan-50 p-3 text-sm font-medium text-spandan-800"><Sparkles className="h-5 w-5 shrink-0" /><span className="flex-1">{t('Not sure which specialty to choose?')}</span><ChevronRight className="h-4 w-4" /></Link>
        </div>
      </div>
    </section>
    <form onSubmit={search} className="glass-card my-6 grid items-end gap-4 p-5 sm:p-6 md:grid-cols-[1fr_1fr_auto]" aria-label={uiText("Find a doctor")}>
      <label className="block text-sm font-semibold text-slate-700">{t('Doctor or hospital')}<span className="field-with-icon mt-2 block"><Search /><input aria-label={uiText("Doctor name or hospital")} className="input-field" placeholder={t('Search by name or hospital')} value={query} onChange={e => setQuery(e.target.value)} /></span></label>
      <label className="block text-sm font-semibold text-slate-700">{t('Specialty')}<select aria-label={uiText("Doctor specialty")} className="input-field mt-2" value={specialty} onChange={e => setSpecialty(e.target.value)}><option value="">{t('All Specializations')}</option>{specializations.map(spec => <option key={spec.id} value={spec.id}>{spec.name}</option>)}</select></label>
      <button className="btn-primary">{t('Search doctors')}<Search className="h-4 w-4" /></button>
    </form>
    {!!specializations.length && <section className="py-10 sm:py-14"><div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><h2 className="page-heading">{t('Find care by specialty')}</h2><p className="page-description">{t('Start with the kind of care you need.')}</p></div><Link to="/doctors?view=booking" className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-spandan-700">{t('View all doctors')}<ArrowRight className="h-4 w-4" /></Link></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{specializations.slice(0, 9).map(spec => <Link key={spec.id} to={`/doctors?view=booking&specialization_id=${spec.id}`} className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 transition-colors hover:border-spandan-300 hover:bg-spandan-50/40"><Stethoscope className="h-5 w-5 shrink-0 text-spandan-600" /><span className="flex-1 text-sm font-semibold">{spec.name}</span><ChevronRight className="h-4 w-4 text-slate-400" /></Link>)}</div></section>}
    <section className="mb-10 flex flex-col justify-between gap-6 rounded-2xl bg-spandan-900 p-6 text-white sm:p-9 md:flex-row md:items-center"><div className="max-w-xl"><h2 className="text-2xl font-semibold tracking-tight">{t('A little preparation makes a better visit.')}</h2><p className="mt-3 text-sm leading-relaxed text-spandan-100">{t('Add your medical history, keep reports in one place, and give your doctor the information they need before you arrive.')}</p></div><Link to={user?.role === 'patient' ? '/dashboard/patient/records' : '/register'} className="btn-secondary shrink-0 border-white text-spandan-900">{t('Prepare for my visit')}<FileHeart className="h-4 w-4" /></Link></section>
  </MainLayout>;
};
