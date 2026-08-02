import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { ApiResponse, DoctorProfile, Specialization } from '../../types';
import { MainLayout } from '../../components/layout/MainLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Search,
  Stethoscope,
} from 'lucide-react';

export const DoctorDiscoveryPage: React.FC = () => {
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const initialSpec = queryParams.get('specialization_id') || '';
  const initialQuery = queryParams.get('query') || '';

  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [loading, setLoading] = useState(true);

  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [selectedSpec, setSelectedSpec] = useState(initialSpec);

  useEffect(() => {
    const fetchSpecs = async () => {
      try {
        const resp = await apiClient.get<ApiResponse<Specialization[]>>('/doctors/specializations');
        if (resp.data.success) setSpecializations(resp.data.data);
      } catch (err) {
        // ignore
      }
    };
    fetchSpecs();
  }, []);

  const fetchDoctors = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('query', searchQuery);
      if (selectedSpec) params.append('specialization_id', selectedSpec);

      const resp = await apiClient.get<ApiResponse<DoctorProfile[]>>(`/doctors?${params.toString()}`);
      if (resp.data.success) {
        setDoctors(resp.data.data);
      }
    } catch (err) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDoctors();
  }, [selectedSpec]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchDoctors();
  };

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Header & Filter Bar */}
        <div className="glass-card p-6 border-slate-200 shadow-md">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-2">Find Verified Doctor Chambers</h1>
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
                onChange={(e) => setSelectedSpec(e.target.value)}
                className="input-field pl-10 bg-white cursor-pointer"
              >
                <option value="">All Specializations</option>
                {specializations.map((spec) => (
                  <option key={spec.id} value={spec.id}>
                    {spec.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-2">
              <button type="submit" className="btn-primary w-full py-2.5 font-semibold">
                Filter Results
              </button>
            </div>
          </form>
        </div>

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
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-spandan-600 to-spandan-400 flex items-center justify-center text-white font-bold text-xl flex-shrink-0 shadow-md shadow-spandan-500/20">
                    {doctor.user?.full_name ? doctor.user.full_name.split(' ').slice(-1)[0][0] : 'DR'}
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold text-lg text-slate-900 hover:text-spandan-600 transition">
                        <Link to={`/doctors/${doctor.id}`}>{doctor.user?.full_name}</Link>
                      </h3>
                      {doctor.is_bmdc_verified && (
                        <Badge variant="success" className="flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> BMDC Verified
                        </Badge>
                      )}
                    </div>

                    <p className="text-sm font-semibold text-spandan-700">
                      {doctor.specialization?.name || 'General Practitioner'}
                      {doctor.qualifications && doctor.qualifications.length > 0 && (
                        <span className="text-slate-500 font-normal ml-2">
                          ({doctor.qualifications.map((q) => q.degree_name).join(', ')})
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
                      {doctor.consultation_fee_default && (
                        <span>
                          Fee: <strong className="text-slate-800">৳{doctor.consultation_fee_default}</strong>
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full md:w-auto self-end md:self-center">
                  <Link
                    to={`/doctors/${doctor.id}`}
                    className="btn-primary py-2.5 px-5 text-sm font-semibold whitespace-nowrap"
                  >
                    View Chambers & Book
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </MainLayout>
  );
};
