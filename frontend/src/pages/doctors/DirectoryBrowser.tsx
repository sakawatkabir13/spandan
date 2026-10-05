import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Building2, ExternalLink, MapPin, Phone, Search, Stethoscope } from 'lucide-react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useLanguage } from '../../context/LanguageContext';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { DirectoryDoctor } from '../../types';

export function DirectoryNotice() {
  const { t } = useLanguage();
  return <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
    {t('Doctor information comes from hospital websites. Contact the hospital to confirm fees, hours and appointments.')}
  </p>;
}

export function SourceLink({ doctor }: { doctor: DirectoryDoctor }) {
  const { t, language } = useLanguage();
  const checked = new Date(`${doctor.source_checked_on}T00:00:00+06:00`).toLocaleDateString(language === 'bn' ? 'bn-BD' : 'en-GB', { timeZone: 'Asia/Dhaka' });
  return <div className="text-xs text-slate-500 space-y-1">
    <a href={doctor.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline text-spandan-700">{t('Official hospital source')}<ExternalLink className="w-3 h-3" aria-hidden="true" /></a>
    <p>{t('Source reviewed')}: {checked}. {t('This is not a confirmation from the doctor.')}</p>
  </div>;
}

export function DirectoryBrowser({ initialQuery = '', specializationId = '' }: { initialQuery?: string; specializationId?: string }) {
  const { t } = useLanguage();
  const [query, setQuery] = useState(initialQuery);
  const [search, setSearch] = useState(initialQuery);
  const [division, setDivision] = useState('');
  const [district, setDistrict] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [categoryId, setCategoryId] = useState(specializationId);
  const [filters, setFilters] = useState({ divisions: [] as string[], districts: [] as string[], specialties: [] as string[] });
  const [rows, setRows] = useState<DirectoryDoctor[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const size = 12;

  useEffect(() => {
    const controller = new AbortController();
    if (categoryId) apiClient.get('/doctors/specializations', { signal: controller.signal }).then(r => {
      const category = r.data.data.find((item: { id: string; name: string }) => item.id === categoryId);
      if (category) setSpecialty(category.name);
    }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    apiClient.get('/directory/filters', { signal: controller.signal }).then(r => setFilters(r.data.data)).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    const controller = new AbortController();
    const params = { query: search, division, district, specialty, specialization_id: specialty ? undefined : categoryId || undefined, skip: page * size, limit: size };
    setLoading(true); setError('');
    apiClient.get('/directory/doctors', { params, signal: controller.signal }).then(r => {
      setRows(r.data.data.items); setTotal(r.data.data.total);
    }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [search, division, district, specialty, categoryId, page, retry]);

  return <div className="space-y-6">
    <section className="glass-card p-6 space-y-4">
      <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">{t('Find doctors across Bangladesh')}</h1>
      <p className="text-slate-600">{t('Explore an initial directory covering all eight divisions, sourced from official hospital websites. This is not a complete national register.')}</p>
      <DirectoryNotice />
      <form className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3" onSubmit={e => { e.preventDefault(); setPage(0); setSearch(query.trim()); }}>
        <label className="sm:col-span-2 lg:col-span-4 text-sm">{t('Doctor, specialty or hospital')}<div className="relative"><Search className="absolute left-3 top-3.5 w-4 h-4 text-slate-400" aria-hidden="true" /><input className="input-field pl-9" maxLength={100} value={query} onChange={e => setQuery(e.target.value)} /></div></label>
        <label className="text-sm">{t('Division')}<select aria-label={t('Division')} className="input-field" value={division} onChange={e => { setDivision(e.target.value); setDistrict(''); setPage(0); }}><option value="">{t('All divisions')}</option>{filters.divisions.map(value => <option key={value}>{value}</option>)}</select></label>
        <label className="text-sm">{t('District')}<select aria-label={t('District')} className="input-field" value={district} onChange={e => { setDistrict(e.target.value); setPage(0); }}><option value="">{t('All districts')}</option>{filters.districts.map(value => <option key={value}>{value}</option>)}</select></label>
        <label className="text-sm">{t('Specialty')}<select aria-label={t('Specialty')} className="input-field" value={specialty} onChange={e => { setSpecialty(e.target.value); setCategoryId(''); setPage(0); }}><option value="">{t('All specialties')}</option>{filters.specialties.map(value => <option key={value}>{value}</option>)}</select></label>
        <button className="btn-primary self-end" type="submit">{t('Search')}</button>
      </form>
    </section>
    {error ? <div role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{error}<button className="btn-secondary ml-3" onClick={() => setRetry(n => n + 1)}>{t('Retry')}</button></div> : loading ? <LoadingSpinner size="lg" text={t('Loading hospital listings...')} /> : <>
      <p role="status" className="text-sm text-slate-600">{total} {t('public hospital listings')} · {t('Page')} {page + 1}</p>
      {!rows.length && <div className="glass-card p-8 space-y-3"><p>{t('No public listings match your search. Try another division or specialty.')}</p><button className="btn-secondary" onClick={() => { setQuery(''); setSearch(''); setDivision(''); setDistrict(''); setSpecialty(''); setCategoryId(''); setPage(0); }}>{t('Reset filters')}</button></div>}
      <div className="grid lg:grid-cols-2 gap-4">{rows.map(doctor => <article key={doctor.id} className="glass-card p-5 space-y-3 flex flex-col">
        <p className="text-xs font-semibold text-amber-800">{t('Public hospital listing')} · {t('Contact hospital')}</p>
        <h2 className="text-lg font-bold"><Link className="hover:text-spandan-700" to={`/directory/${doctor.id}`}>{doctor.full_name}</Link></h2>
        {doctor.native_name && <p lang="bn" className="text-sm text-slate-600">{doctor.native_name}</p>}
        <p className="flex gap-2 text-spandan-700 text-sm"><Stethoscope className="w-4 h-4 shrink-0" aria-hidden="true" />{doctor.specialty}</p>
        {doctor.qualifications && <p className="text-sm text-slate-600">{doctor.qualifications}</p>}
        <p className="flex gap-2 text-sm"><Building2 className="w-4 h-4 shrink-0" aria-hidden="true" />{doctor.institution}</p>
        <p className="flex gap-2 text-sm text-slate-600"><MapPin className="w-4 h-4 shrink-0" aria-hidden="true" />{doctor.district}, {doctor.division}</p>
        <div className="flex flex-wrap gap-3 pt-2 mt-auto"><Link className="btn-secondary text-sm" to={`/directory/${doctor.id}`}>{t('View hospital listing')}</Link>{doctor.appointment_phone && <a className="btn-secondary text-sm" href={`tel:${doctor.appointment_phone}`}><Phone className="w-4 h-4" aria-hidden="true" />{doctor.appointment_phone}</a>}</div>
        {doctor.booking_status === 'demo_only' && doctor.demo_doctor_id && <Link className="btn-primary text-sm" to={`/doctors/${doctor.demo_doctor_id}`}>{t('Book appointment')}</Link>}
        <SourceLink doctor={doctor} />
      </article>)}</div>
      {total > size && <nav aria-label={t('Directory results pages')} className="flex gap-3 items-center"><button className="btn-secondary" disabled={page === 0} onClick={() => setPage(p => p - 1)}>{t('Previous')}</button><span>{t('Page')} {page + 1} / {Math.ceil(total / size)}</span><button className="btn-secondary" disabled={(page + 1) * size >= total} onClick={() => setPage(p => p + 1)}>{t('Next')}</button></nav>}
    </>}
  </div>;
}
