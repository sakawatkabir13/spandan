import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { MainLayout } from '../../components/layout/MainLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { useLanguage } from '../../context/LanguageContext';
import { DirectoryDoctor } from '../../types';
import { DirectoryNotice, SourceLink } from './DirectoryBrowser';

export function DirectoryDetailPage() {
  const { id } = useParams();
  const { t } = useLanguage();
  const [doctor, setDoctor] = useState<DirectoryDoctor | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setDoctor(null); setError('');
    apiClient.get(`/directory/doctors/${id}`, { signal: controller.signal }).then(r => setDoctor(r.data.data)).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [id]);
  return <MainLayout><div className="space-y-6 max-w-3xl mx-auto">
    <Link className="text-spandan-700 underline" to="/doctors?view=directory">{t('Back to hospital directory')}</Link>
    {error ? <p role="alert" className="bg-red-50 rounded-xl p-4 text-red-800">{error}</p> : !doctor ? <LoadingSpinner size="lg" /> : <article className="glass-card p-6 space-y-5">
      <p className="text-amber-800 text-sm font-semibold">{t('Public hospital listing')}</p>
      <h1 className="text-2xl sm:text-3xl font-bold">{doctor.full_name}</h1>
      {doctor.native_name && <p lang="bn">{doctor.native_name}</p>}
      <DirectoryNotice />
      <dl className="space-y-4">
        <div><dt className="font-semibold">{t('Specialty')}</dt><dd>{doctor.specialty}</dd></div>
        {doctor.qualifications && <div><dt className="font-semibold">{t('Qualifications published by hospital')}</dt><dd>{doctor.qualifications}</dd></div>}
        <div><dt className="font-semibold">{t('Hospital or chamber')}</dt><dd>{doctor.institution}</dd><dd>{doctor.address || `${doctor.district}, ${doctor.division}`}</dd></div>
        <div><dt className="font-semibold">{t('Published consultation hours')}</dt><dd>{doctor.published_hours || t('Hours are not reliably published. Contact the hospital.')}</dd><dd className="text-sm text-amber-800">{t('Published hours may have changed. They do not reserve an appointment or show live availability.')}</dd></div>
        <div><dt className="font-semibold">{t('Consultation fee')}</dt><dd>{t('Confirm current fees directly with the hospital.')}</dd></div>
      </dl>
      <div className="flex flex-wrap gap-3">{doctor.appointment_phone && <a className="btn-primary" href={`tel:${doctor.appointment_phone}`}>{t('Call hospital')}: {doctor.appointment_phone}</a>}<a className="btn-secondary" href={doctor.contact_source_url || doctor.source_url} target="_blank" rel="noopener noreferrer">{t('Visit hospital website')}</a></div>
      {doctor.booking_status === 'demo_only' && doctor.demo_doctor_id && <div className="rounded-xl bg-spandan-50 p-4 space-y-3"><p>{t('This profile has an academic demo account with simulated fees and availability. It does not book a real hospital visit.')}</p><Link className="btn-primary" to={`/doctors/${doctor.demo_doctor_id}`}>{t('Book demo appointment')}</Link></div>}
      <SourceLink doctor={doctor} />
      <p className="text-sm text-slate-500">{t('To request a correction or removal, contact')} <a className="underline" href="mailto:community.cuetinsights@gmail.com">community.cuetinsights@gmail.com</a>.</p>
    </article>}
  </div></MainLayout>;
}
