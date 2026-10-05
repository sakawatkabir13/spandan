import { useLanguage } from '../../context/LanguageContext';
import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { ApiResponse, DoctorProfile, Specialization } from '../../types';
import { MainLayout } from '../../components/layout/MainLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { DirectoryBrowser } from './DirectoryBrowser';
import { Badge } from '../../components/common/Badge';
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Search,
  Stethoscope,
} from 'lucide-react';

export const DoctorDiscoveryPage: React.FC = () => {
  const { t } = useLanguage();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const initialSpec = queryParams.get('specialization_id') || '';
  const bookable = queryParams.get('view') === 'booking' || !!initialSpec;
  const initialQuery = queryParams.get('query') || '';

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

  const fetchDoctors = async () => {
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

      const resp = await apiClient.get<ApiResponse<DoctorProfile[]>>(`/doctors?${params.toString()}`);
      if (resp.data.success) {
        setHasMore(resp.data.data.length > 20);
        setDoctors(resp.data.data.slice(0, 20));
        setLoadError('');
      }
    } catch (err) {
      setLoadError('Unable to load doctor information. Please refresh to try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (bookable) fetchDoctors();
  }, [selectedSpec, page, bookable]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (page) setPage(0); else fetchDoctors();
  };

  return (
    <MainLayout>
      <nav aria-label={t('Doctor directory options')} className="flex flex-wrap gap-3 mb-6"><Link to="/doctors?view=directory" aria-current={!bookable ? 'page' : undefined} className={!bookable ? 'btn-primary' : 'btn-secondary'}>{t('Public hospital directory')}</Link><Link to="/doctors?view=booking" aria-current={bookable ? 'page' : undefined} className={bookable ? 'btn-primary' : 'btn-secondary'}>{t('Book on Spandan')}</Link></nav>
      {!bookable ? <DirectoryBrowser initialQuery={initialQuery} /> : <>
      {loadError && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{loadError}</p>}
      <div className="space-y-8">
        {/* Header & Filter Bar */}
        <div className="glass-card p-6 border-slate-200 shadow-md">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-2">{t('Find Verified Doctor Chambers')}</h1>
          <p className="text-sm text-slate-600 mb-6">
            Search by specialty, doctor name, or hospital to book instant online serials and track live chambers.
          </p>

          <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-3">
            <div className="md:col-span-6 relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
              <input
                type="text"
                placeholder="Doctor name, qualification, or hospital..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-field pl-10 bg-white"
              />
            </div>

            <div className="md:col-span-4 relative">
              <Stethoscope className="w-4 h-4 text-spandan-600 absolute left-3.5 top-3.5 pointer-events-none" />
              <select
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

            <label className="md:col-span-4 text-sm">{t('District')}<input value={district} onChange={e => setDistrict(e.target.value)} className="input-field" /></label>
            <label className="md:col-span-4 text-sm">{t('Maximum fee (৳)')}<input type="number" min={0} value={fee} onChange={e => setFee(e.target.value)} className="input-field" /></label>
            <label className="md:col-span-4 text-sm">{t('Available on')}<input type="date" value={availableOn} onChange={e => setAvailableOn(e.target.value)} className="input-field" /></label>
            <div className="md:col-span-2">
              <button type="submit" className="btn-primary w-full py-2.5 font-semibold">{t('Filter Results')}</button>
            </div>
          </form>
        </div>

        <nav aria-label="Doctor results pages" className="flex gap-3 items-center"><button className="btn-secondary" disabled={loading || page === 0} onClick={() => setPage(p => p - 1)}>{t('Previous')}</button><span>Page {page + 1}</span><button className="btn-secondary" disabled={loading || !hasMore} onClick={() => setPage(p => p + 1)}>{t('Next')}</button></nav>
        {/* Doctor List */}
        {loading ? (
          <LoadingSpinner size="lg" text="Searching doctors..." />
        ) : doctors.length === 0 ? (
          <div className="glass-card p-12 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mx-auto">
              <Stethoscope className="w-8 h-8" />
            </div>
            <h3 className="font-semibold text-lg text-slate-800">No doctors found matching your criteria</h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              Try adjusting your search terms or select "All Specializations" to explore all available chamber physicians.
            </p>
            <button
              onClick={() => {
                setSearchQuery('');
                setSelectedSpec('');
              }}
              className="btn-secondary mx-auto text-sm"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {doctors.map((doctor) => (
              <div
                key={doctor.id}
                className="glass-card p-6 border-slate-200/80 hover:border-spandan-400 transition flex flex-col md:flex-row items-start md:items-center justify-between gap-6"
              >
                <div className="flex items-start gap-4">
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

                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold text-lg text-slate-900 hover:text-spandan-600 transition">
                        <Link to={`/doctors/${doctor.id}`}>{doctor.full_name}</Link>
                      </h3>
                      {(doctor.verification_status === 'approved') && (
                        <Badge variant="success" className="flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> BMDC Verified
                        </Badge>
                      )}
                    </div>

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
                      <span>
                        <strong className="text-slate-700">{doctor.years_of_experience}</strong> years experience
                      </span>

                    </div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full md:w-auto self-end md:self-center">
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
