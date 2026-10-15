import { I18nText } from '../../context/LanguageContext';
import { useLanguage } from '../../context/LanguageContext';
import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { ApiResponse, DoctorProfile, Specialization } from '../../types';
import { MainLayout } from '../../components/layout/MainLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { DirectoryBrowser } from './DirectoryBrowser';
import { Badge } from '../../components/common/Badge';
import { DoctorBookingFacts, DoctorFacts, SaveDoctorButton } from '../../components/common/DoctorBookingFacts';
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Search,
  Stethoscope,
} from 'lucide-react';

export const DoctorDiscoveryPage: React.FC = () => {
  const { t: uiText } = useLanguage();
  const { t } = useLanguage();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const initialSpec = queryParams.get('specialization_id') || '';
  const bookable = queryParams.get('view') === 'booking';
  const initialQuery = queryParams.get('query') || '';

  const [searchRevision, setSearchRevision] = useState(0);
  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [selectedSpec, setSelectedSpec] = useState(initialSpec);
  const [district, setDistrict] = useState('');
  const [fee, setFee] = useState('');
  const [availableOn, setAvailableOn] = useState('');
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [facts, setFacts] = useState<Record<string, DoctorFacts>>({});
  useEffect(() => {
    if (!doctors.length) { setFacts({}); return; }
    const controller = new AbortController();
    const params = new URLSearchParams(); doctors.forEach(d => params.append('doctor_ids', d.id));
    void apiClient.get(`/discovery/booking-facts?${params}`, { signal: controller.signal }).then(r => setFacts(r.data.data)).catch(() => {});
    return () => controller.abort();
  }, [doctors]);

  useEffect(() => {
    const fetchSpecs = async () => {
      try {
        const resp = await apiClient.get<ApiResponse<Specialization[]>>('/doctors/specializations');
        if (resp.data.success) setSpecializations(resp.data.data);
      } catch (err) {
        setLoadError('Unable to load doctor information. Please refresh to try again.');
      }
    };
    if (bookable) fetchSpecs();
  }, [bookable]);

  const fetchDoctors = async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('query', searchQuery);
      if (selectedSpec) params.append('specialization_id', selectedSpec);
      if (district) params.append('district', district);
      if (fee) params.append('max_fee', fee);
      if (availableOn) params.append('available_on', availableOn);
      params.append('skip', String(page * 20));
      params.append('limit', '21');

      const resp = await apiClient.get<ApiResponse<DoctorProfile[]>>(`/doctors?${params.toString()}`, { signal });
      if (resp.data.success) {
        setHasMore(resp.data.data.length > 20);
        setDoctors(resp.data.data.slice(0, 20));
        setLoadError('');
      }
    } catch (err) {
      if (signal?.aborted) return;
      setLoadError('Unable to load doctor information. Please refresh to try again.');
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    if (bookable) void fetchDoctors(controller.signal);
    return () => controller.abort();
  }, [selectedSpec, page, bookable, searchRevision]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0); setSearchRevision(value => value + 1);
  };

  return (
    <MainLayout>
      <nav aria-label={t('Doctor directory options')} className="segmented-control mb-6 w-fit max-w-full"><Link to="/doctors?view=directory" aria-current={!bookable ? 'page' : undefined}>{t('Public hospital directory')}</Link><Link to="/doctors?view=booking" aria-current={bookable ? 'page' : undefined}>{t('Book on Spandan')}</Link></nav>
      {!bookable ? <DirectoryBrowser key={location.search} initialQuery={initialQuery} specializationId={initialSpec} /> : <>
      {loadError && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{loadError}</p>}
      <div className="space-y-8">
        <div className="flex flex-wrap items-center gap-2"><span className="text-xs text-slate-500"><I18nText text="Browse common visit reasons" /></span>{[
          ['General health concerns', 'general medicine'], ["Children's health", 'pediatrics'], ['Heart & blood pressure', 'cardiology'], ['Skin, hair & nails', 'dermatology'], ['Bones & joints', 'orthopedics'], ['Ear, nose & throat', 'ent'],
        ].map(([label, name]) => { const spec = specializations.find(s => s.name.toLowerCase() === name); return spec && <button type="button" key={name} className="rounded-full border border-spandan-200 bg-white px-3 py-2 text-xs font-medium text-spandan-800 transition-colors hover:bg-spandan-50" onClick={() => { setPage(0); setSelectedSpec(spec.id); }}><I18nText text={label} /></button>; })}</div>
        {/* Header & Filter Bar */}
        <div className="glass-card p-6 border-slate-200 shadow-md">
          <h1 className="page-heading mb-2">{t('Find Verified Doctor Chambers')}</h1>
          <p className="text-sm text-slate-600 mb-6">
             <I18nText text={"Search by specialty, doctor name, or hospital to book instant online serials and track live chambers."} /> </p>

          <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            <div className="sm:col-span-2 xl:col-span-2 field-with-icon">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
              <input
                type="text"
                aria-label={uiText("Search doctor name or hospital")}
                placeholder={uiText("Doctor name, qualification, or hospital...")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-field pl-10 bg-white"
              />
            </div>

            <div className="field-with-icon">
              <Stethoscope className="w-4 h-4 text-spandan-600 absolute left-3.5 top-3.5 pointer-events-none" />
              <select
                aria-label={uiText("Specialization")}
                value={selectedSpec}
                onChange={(e) => { setPage(0); setSelectedSpec(e.target.value); }}
                className="input-field pl-10 bg-white cursor-pointer"
              >
                <option value="">{t('All Specializations')}</option>
                {specializations.map((spec) => (
                  <option key={spec.id} value={spec.id}>
                    {spec.name}
                  </option>
                ))}
              </select>
            </div>

            <label className="block text-sm">{t('District')}<input value={district} onChange={e => setDistrict(e.target.value)} className="input-field" /></label>
            <label className="block text-sm">{t('Maximum fee (৳)')}<input type="number" min={0} value={fee} onChange={e => setFee(e.target.value)} className="input-field" /></label>
            <label className="block text-sm">{t('Available on')}<input type="date" value={availableOn} onChange={e => setAvailableOn(e.target.value)} className="input-field" /></label>
            <div className="sm:col-span-2 xl:col-span-3 flex flex-wrap gap-3">
              <button type="submit" className="btn-primary py-2.5 font-semibold">{t('Filter Results')}</button><button type="button" className="btn-secondary" onClick={() => { setSearchQuery(''); setSelectedSpec(''); setDistrict(''); setFee(''); setAvailableOn(''); setPage(0); setSearchRevision(value => value + 1); }}> <I18nText text={"Clear filters"} /> </button>
            </div>
          </form>
        </div>

        <nav aria-label={uiText("Doctor results pages")} className="flex gap-3 items-center"><button className="btn-secondary" disabled={loading || page === 0} onClick={() => setPage(p => p - 1)}>{t('Previous')}</button><span> <I18nText text={"Page"} /> {page + 1}</span><button className="btn-secondary" disabled={loading || !hasMore} onClick={() => setPage(p => p + 1)}>{t('Next')}</button></nav>
        {/* Doctor List */}
        {loading ? (
          <LoadingSpinner size="lg" text={uiText("Searching doctors...")} />
        ) : doctors.length === 0 ? (
          <div className="glass-card p-12 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mx-auto">
              <Stethoscope className="w-8 h-8" />
            </div>
            <h3 className="font-semibold text-lg text-slate-800"> <I18nText text={"No doctors found matching your criteria"} /> </h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
               <I18nText text={"Try adjusting your search terms or select \"All Specializations\" to explore all available chamber physicians."} /> </p>
            <button
              onClick={() => {
                setSearchQuery(''); setSelectedSpec(''); setDistrict(''); setFee(''); setAvailableOn(''); setPage(0); setSearchRevision(value => value + 1);
              }}
              className="btn-secondary mx-auto text-sm"
            >
               <I18nText text={"Reset Filters"} /> </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {doctors.map((doctor) => (
              <div
                key={doctor.id}
                className="glass-card p-5 sm:p-6 border-slate-200/80 flex flex-col xl:flex-row items-start xl:items-center justify-between gap-5"
              >
                <div className="flex min-w-0 items-start gap-4">
                  {doctor.profile_photo_url ? (
                    <img
                      src={doctor.profile_photo_url}
                      alt={`${doctor.full_name} profile`}
                      className="w-14 h-14 rounded-2xl object-cover flex-shrink-0 shadow-md shadow-spandan-500/20"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-spandan-600 to-spandan-400 flex items-center justify-center text-white font-bold text-xl flex-shrink-0 shadow-md shadow-spandan-500/20" aria-hidden="true">
                      {doctor.full_name ? doctor.full_name.split(' ').slice(-1)[0][0] : 'DR'}
                    </div>
                  )}

                  <div className="min-w-0 space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold text-lg text-slate-900 hover:text-spandan-600 transition">
                        <Link to={`/doctors/${doctor.id}`}>{doctor.full_name}</Link>
                      </h3>
                      {(doctor.verification_status === 'approved') && (
                        <Badge variant="success" className="flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> {doctor.is_demo ? t('Hospital-sourced profile') : 'BMDC Verified'}
                        </Badge>
                      )}
                    </div>
                    <DoctorBookingFacts facts={facts[doctor.id]} sourced={doctor.is_demo} />

                    <p className="text-sm font-semibold text-spandan-700">
                      {doctor.specializations.map((s) => s.name).join(', ') || 'General Practitioner'}
                      {doctor.qualifications && doctor.qualifications.length > 0 && (
                        <span className="text-slate-500 font-normal ml-2">
                          ({doctor.qualifications.map((q) => q.title).join(', ')})
                        </span>
                      )}
                    </p>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
                      {doctor.current_workplace && (
                        <span className="flex items-center gap-1">
                          <Building2 className="w-3.5 h-3.5 text-slate-400" />
                          {doctor.current_workplace}
                        </span>
                      )}
                      {!doctor.is_demo && doctor.years_of_experience > 0 && <span>
                        <strong className="text-slate-700">{doctor.years_of_experience}</strong>  <I18nText text={"years experience"} /> </span>}

                    </div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full md:w-auto self-end md:self-center">
                  <SaveDoctorButton doctorId={doctor.id} />
                  <Link
                    to={`/doctors/${doctor.id}`}
                    className="btn-primary py-2.5 px-5 text-sm font-semibold whitespace-nowrap"
                  >{t('View Chambers & Book')}<ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      </>}
    </MainLayout>
  );
};
