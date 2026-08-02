import React, { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ApiResponse, DoctorProfile } from '../../types';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import { CheckCircle2, Mail, Phone, Stethoscope } from 'lucide-react';

export const ProfilePage: React.FC = () => {
  const { user } = useAuth();
  const [docProfile, setDocProfile] = useState<DoctorProfile | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user?.role === 'doctor') {
      setLoading(true);
      apiClient
        .get<ApiResponse<DoctorProfile[]>>('/doctors/me/profile')
        .then((resp) => {
          if (resp.data.success && resp.data.data.length > 0) {
            setDocProfile(resp.data.data[0]);
          }
        })
        .finally(() => setLoading(false));
    }
  }, [user]);

  if (!user) return null;

  return (
    <DashboardLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="glass-card p-8 border-slate-200 space-y-6">
          <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6 pb-6 border-b border-slate-100">
            <div className="w-20 h-20 rounded-2xl bg-spandan-600 text-white font-extrabold text-3xl flex items-center justify-center shadow-lg shadow-spandan-500/25 flex-shrink-0">
              {user.full_name?.charAt(0) || 'U'}
            </div>

            <div className="space-y-1.5 text-center sm:text-left flex-1">
              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-3">
                <h2 className="text-2xl font-bold text-slate-900">{user.full_name || 'Spandan User'}</h2>
                <Badge variant="primary" className="uppercase font-bold">
                  {user.role}
                </Badge>
              </div>

              <div className="flex flex-wrap justify-center sm:justify-start gap-4 text-xs text-slate-600 pt-1">
                <span className="flex items-center gap-1.5">
                  <Mail className="w-4 h-4 text-slate-400" /> {user.email}
                </span>
                <span className="flex items-center gap-1.5">
                  <Phone className="w-4 h-4 text-slate-400" /> {user.phone_number || 'No phone set'}
                </span>
              </div>
            </div>
          </div>

          {loading ? (
            <LoadingSpinner text="Loading practitioner details..." />
          ) : docProfile ? (
            <div className="space-y-4 bg-slate-50 p-6 rounded-2xl border border-slate-200/80">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200/60">
                <h3 className="font-bold text-sm text-slate-800 uppercase tracking-wider flex items-center gap-2">
                  <Stethoscope className="w-4 h-4 text-spandan-600" /> BMDC & Professional Status
                </h3>
                {docProfile.is_bmdc_verified ? (
                  <Badge variant="success" className="flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> BMDC Verified
                  </Badge>
                ) : (
                  <Badge variant="warning">Pending Verification</Badge>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-xs text-slate-400 uppercase block font-medium">BMDC Registration No.</span>
                  <strong className="text-slate-800">{docProfile.medical_registration_number}</strong>
                </div>
                <div>
                  <span className="text-xs text-slate-400 uppercase block font-medium">Specialty Department</span>
                  <strong className="text-spandan-700">{docProfile.specialization?.name}</strong>
                </div>
                <div>
                  <span className="text-xs text-slate-400 uppercase block font-medium">Current Workplace</span>
                  <strong className="text-slate-800">{docProfile.current_workplace || 'Private Practice'}</strong>
                </div>
                <div>
                  <span className="text-xs text-slate-400 uppercase block font-medium">Experience</span>
                  <strong className="text-slate-800">{docProfile.years_of_experience} Years</strong>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </DashboardLayout>
  );
};
