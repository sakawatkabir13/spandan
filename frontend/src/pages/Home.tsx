import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Activity, ArrowRight, CalendarDays, Check, ChevronRight, Clock3, FileHeart, Search, ShieldCheck, Sparkles, Stethoscope } from 'lucide-react';
import { apiClient } from '../api/client';
import { ApiResponse, Specialization } from '../types';
import { MainLayout } from '../components/layout/MainLayout';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';

export const Home = () => {
  const { t } = useLanguage();
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [query, setQuery] = useState('');
  const [specialty, setSpecialty] = useState('');
  const { user } = useAuth();
  const navigate = useNavigate();
  const workspace = user ? `/dashboard/${user.role === 'administrator' ? 'admin' : user.role}` : '/login';
  const preparation = user ? user.role === 'patient' ? '/dashboard/patient/records' : workspace : '/register';
  useEffect(() => { void apiClient.get<ApiResponse<Specialization[]>>('/doctors/specializations').then(r => setSpecializations(r.data.data)).catch(() => {}); }, []);
  const search = (event: React.FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams({ view: 'booking' });
    if (query.trim()) params.set('query', query.trim());
    if (specialty) params.set('specialization_id', specialty);
    navigate(`/doctors?${params}`);
  };
  return <MainLayout>
    <section className="brand-hero relative isolate mb-10 overflow-hidden rounded-3xl border border-slate-800 p-6 text-white shadow-xl shadow-slate-900/10 sm:mb-14 sm:p-10 lg:p-14">
      <svg aria-hidden="true" viewBox="0 0 1200 180" fill="none" className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 w-full text-spandan-400/10"><path d="M0 100H220L240 85L263 120L296 26L330 155L355 100H700L722 80L750 120L786 30L818 150L846 100H1200" stroke="currentColor" strokeWidth="2" /></svg>
      <div className="grid items-center gap-10 lg:grid-cols-[1.35fr_.65fr] lg:gap-12">
        <div className="min-w-0">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-spandan-400/25 bg-spandan-400/10 px-3.5 py-2 text-xs font-semibold text-spandan-200"><Sparkles className="h-4 w-4" />{t('AI-Assisted Private Chamber Booking')}</p>
          <h1 className="max-w-2xl text-[2.4rem] font-bold leading-[1.12] tracking-tight sm:text-5xl lg:text-[3.65rem]">{t('End the Chamber Waiting Room')} <span className="bg-gradient-to-r from-spandan-300 to-emerald-200 bg-clip-text text-transparent">{t('Uncertainty.')}</span></h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-slate-300">{t('Find your specialist, reserve a serial, and follow the queue before you travel. Your appointments, reports, and next steps stay together.')}</p>
          <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3 text-xs text-slate-300"><span className="inline-flex items-center gap-2"><Clock3 className="h-4 w-4 text-spandan-300" />{t('Live serial tracking')}</span><span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-spandan-300" />{t('Patient-controlled sharing')}</span></div>
        </div>
        <div className="brand-glass relative hidden rounded-2xl p-6 lg:block">
          <div className="mb-6 flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl border border-spandan-400/20 bg-spandan-400/10 text-spandan-300"><Activity className="h-6 w-6" /></span><div><p className="font-semibold">{t('Your visit, connected.')}</p><p className="mt-1 text-xs text-slate-400">{t('From booking to follow-up')}</p></div></div>
          <div className="space-y-5">{[
            { icon: Stethoscope, title: 'Find the right doctor', text: 'Specialties, chambers, and transparent fees' },
            { icon: FileHeart, title: 'Arrive prepared', text: 'Share the records you choose for your visit' },
            { icon: CalendarDays, title: 'Stay in control', text: 'Your serial, payment, and follow-up in one place' },
          ].map(item => <div key={item.title} className="flex items-start gap-3"><span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/5 text-spandan-200"><item.icon className="h-4 w-4" /></span><div className="min-w-0"><p className="text-sm font-medium text-white">{t(item.title)}</p><p className="mt-1 text-xs leading-relaxed text-slate-400">{t(item.text)}</p></div></div>)}</div>
          <Link to={workspace} className="mt-6 flex items-center justify-between border-t border-white/10 pt-4 text-xs font-semibold text-spandan-200 transition-colors hover:text-white">{t('Manage my visits')}<ArrowRight className="h-4 w-4" /></Link>
        </div>
      </div>
      <form onSubmit={search} aria-label={t('Find a doctor')} className="brand-hero-search relative mt-9 grid gap-3 rounded-2xl border border-white/70 bg-white p-3 text-slate-900 sm:grid-cols-[1fr_1fr_auto] lg:mt-10">
        <label className="flex min-w-0 items-center gap-3 rounded-xl bg-slate-50 px-3 py-1 sm:bg-transparent"><Search className="h-5 w-5 shrink-0 text-slate-400" /><span className="sr-only">{t('Doctor name or hospital')}</span><input aria-label={t('Doctor name or hospital')} placeholder={t('Doctor name or hospital...')} className="min-h-11 w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-slate-400" value={query} onChange={e => setQuery(e.target.value)} /></label>
        <label className="flex min-w-0 items-center gap-3 rounded-xl bg-slate-50 px-3 py-1 sm:border-l sm:border-slate-200 sm:bg-transparent"><Stethoscope className="h-5 w-5 shrink-0 text-spandan-700" /><span className="sr-only">{t('Doctor specialty')}</span><select aria-label={t('Doctor specialty')} className="min-h-11 w-full min-w-0 bg-transparent text-sm outline-none" value={specialty} onChange={e => setSpecialty(e.target.value)}><option value="">{t('All Specializations')}</option>{specializations.map(spec => <option key={spec.id} value={spec.id}>{spec.name}</option>)}</select></label>
        <button className="btn-primary sm:px-6">{t('Search doctors')}<ArrowRight className="h-4 w-4" /></button>
      </form>
    </section>
    <section className="mb-12 grid gap-5 md:grid-cols-3 sm:mb-16">{[
      { icon: Clock3, title: 'Live Serial Tracking', text: 'Follow your running serial and queue updates before travelling. Arrival windows are estimates and can change.', color: 'bg-spandan-50 text-spandan-700', path: workspace, link: 'Manage my visits' },
      { icon: Sparkles, title: 'AI Symptom Triage', text: 'Not sure which specialist to see? Explore specialist categories and emergency alerts. This guidance does not provide a diagnosis.', color: 'bg-blue-50 text-blue-700', path: '/ai-triage', link: 'Explore symptom guidance' },
      { icon: FileHeart, title: 'Private Health Records', text: 'Keep your history and reports together. Choose what to share with your booked doctor, including separate charts for family members.', color: 'bg-amber-50 text-amber-700', path: preparation, link: 'Prepare for my visit' },
    ].map(item => <article key={item.title} className="glass-card glass-card-hover flex flex-col p-6"><span className={`brand-feature-icon mb-5 flex h-12 w-12 items-center justify-center rounded-2xl ${item.color}`}><item.icon className="h-6 w-6" /></span><h2 className="text-lg font-bold text-slate-900">{t(item.title)}</h2><p className="mb-5 mt-2 flex-1 text-sm leading-relaxed text-slate-600">{t(item.text)}</p><Link to={item.path} className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-spandan-700 hover:text-spandan-800">{t(item.link)}<ArrowRight className="h-4 w-4" /></Link></article>)}</section>
    {!!specializations.length && <section className="mb-12 sm:mb-16"><div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><h2 className="page-heading">{t('Find care by specialty')}</h2><p className="page-description">{t('Start with the kind of care you need.')}</p></div><Link to="/doctors?view=booking" className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-spandan-700">{t('View all doctors')}<ArrowRight className="h-4 w-4" /></Link></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{specializations.slice(0, 9).map(spec => <Link key={spec.id} to={`/doctors?view=booking&specialization_id=${spec.id}`} className="group flex items-center gap-4 rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm shadow-slate-900/[.02] transition duration-200 hover:-translate-y-0.5 hover:border-spandan-300 hover:shadow-md hover:shadow-spandan-600/5"><span className="rounded-lg bg-spandan-50 p-2 text-spandan-700"><Stethoscope className="h-5 w-5 shrink-0" /></span><span className="flex-1 text-sm font-semibold">{spec.name}</span><ChevronRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-1" /></Link>)}</div></section>}
    <section className="brand-hero mb-10 flex flex-col justify-between gap-6 rounded-3xl p-7 text-white shadow-xl shadow-slate-900/10 sm:p-10 md:flex-row md:items-center"><div className="max-w-xl"><p className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-spandan-200"><Check className="h-4 w-4" />{t('A little preparation makes a better visit.')}</p><h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t('More time for care. Less time managing it.')}</h2><p className="mt-4 text-sm leading-relaxed text-slate-300">{t('Add your medical history, keep reports in one place, and give your doctor the information they need before you arrive.')}</p></div><Link to={preparation} className="btn-primary shrink-0">{t('Prepare for my visit')}<FileHeart className="h-4 w-4" /></Link></section>
  </MainLayout>;
};
