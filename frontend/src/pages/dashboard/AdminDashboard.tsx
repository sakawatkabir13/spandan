import React, { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import { ApiResponse, AuditLog, DoctorProfile } from '../../types';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import {
  CheckCircle2,
  History,
  ShieldCheck,
  Stethoscope,
  XCircle,
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const [loadError, setLoadError] = useState('');
  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  // Reject Modal
  const [rejectTarget, setRejectTarget] = useState<DoctorProfile | null>(null);
  const [rejectNotes, setRejectNotes] = useState('');
  const [rejectSubmitting, setRejectSubmitting] = useState(false);

  const fetchDoctors = async () => {
    setLoading(true);
    try {
      const [resp, auditResp] = await Promise.all([
        apiClient.get<ApiResponse<DoctorProfile[]>>('/doctors/admin/all'),
        apiClient.get<ApiResponse<AuditLog[]>>('/users/audit-logs?limit=25'),
      ]);
      if (resp.data.success) {
        setDoctors(resp.data.data);
      }
      if (auditResp.data.success) {
        setAuditLogs(
          auditResp.data.data.filter(
            (entry): entry is AuditLog => typeof entry?.action === 'string' && typeof entry?.created_at === 'string',
          ),
        );
      }
    } catch (err) {
      setLoadError('Unable to load the latest data. Please refresh to try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDoctors();
  }, []);

  const handleVerify = async (doctor: DoctorProfile, verify: boolean, notes?: string) => {
    try {
      await apiClient.post(`/doctors/${doctor.id}/verify`, {
        status: verify ? 'approved' : 'rejected',
        verification_notes: notes || (verify ? 'BMDC verified by System Administrator' : 'Verification rejected'),
      });
      await fetchDoctors();
      return true;
    } catch (err: any) {
      setLoadError(err.response?.data?.error?.message || 'Failed to update doctor verification.');
      return false;
    }
  };

  const handleConfirmReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rejectTarget) return;
    setRejectSubmitting(true);
    const saved = await handleVerify(rejectTarget, false, rejectNotes);
    setRejectSubmitting(false);
    if (!saved) return;
    setRejectTarget(null);
    setRejectNotes('');
  };

  const pendingCount = doctors.filter((d) => d.verification_status === 'pending').length;
  const verifiedCount = doctors.filter((d) => (d.verification_status === 'approved')).length;

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {loadError && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-800">{loadError}</p>}
        {/* Header */}
        <div className="glass-card p-6 border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">System Administration & BMDC Verification</h1>
            <p className="text-sm text-slate-600">
              Audit participating practitioners, verify Bangladesh Medical & Dental Council (BMDC) credentials.
            </p>
          </div>

          <div className="flex gap-4">
            <div className="bg-amber-50 border border-amber-200 px-4 py-2 rounded-xl text-center">
              <span className="text-[11px] font-bold uppercase text-amber-800 block">Pending Audit</span>
              <span className="text-xl font-extrabold text-amber-900">{pendingCount}</span>
            </div>
            <div className="bg-emerald-50 border border-emerald-200 px-4 py-2 rounded-xl text-center">
              <span className="text-[11px] font-bold uppercase text-emerald-800 block">BMDC Verified</span>
              <span className="text-xl font-extrabold text-emerald-900">{verifiedCount}</span>
            </div>
          </div>
        </div>

        {loading ? (
          <LoadingSpinner size="lg" text="Loading doctor verification registry..." />
        ) : doctors.length === 0 ? (
          <div className="glass-card p-12 text-center text-slate-500">No doctors registered yet.</div>
        ) : (
          <div className="glass-card p-6 border-slate-200 space-y-4">
            <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2 pb-3 border-b border-slate-100">
              <ShieldCheck className="w-5 h-5 text-spandan-600" /> Practitioner Audit Registry
            </h3>

            <div className="divide-y divide-slate-100">
              {doctors.map((doc) => (
                <div key={doc.id} className="py-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-spandan-100 text-spandan-800 font-bold text-base flex items-center justify-center flex-shrink-0">
                      <Stethoscope className="w-6 h-6 text-spandan-600" />
                    </div>

                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="font-bold text-base text-slate-900">{doc.full_name}</h4>
                        <Badge variant={(doc.verification_status === 'approved') ? 'success' : 'warning'}>
                          {(doc.verification_status === 'approved') ? 'VERIFIED BMDC' : doc.verification_status.toUpperCase()}
                        </Badge>
                      </div>

                      <p className="text-sm font-semibold text-spandan-700">
                        {doc.specializations.map((s) => s.name).join(', ')} | BMDC Reg: <strong className="text-slate-900">{doc.medical_registration_number}</strong>
                      </p>

                      <p className="text-xs text-slate-500">
                        Workplace: {doc.current_workplace || 'Private Practice'} | Experience: {doc.years_of_experience} years
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end md:self-center">
                    {doc.verification_status !== 'approved' ? (
                      <>
                        <button
                          onClick={() => handleVerify(doc, true)}
                          className="btn-primary py-2 px-4 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 shadow-none flex items-center gap-1.5"
                        >
                          <CheckCircle2 className="w-4 h-4" /> Approve BMDC
                        </button>
                        <button
                          onClick={() => setRejectTarget(doc)}
                          className="btn-secondary py-2 px-4 text-xs font-semibold text-red-600 border-red-200 hover:bg-red-50 flex items-center gap-1.5"
                        >
                          <XCircle className="w-4 h-4" /> Reject
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleVerify(doc, false, 'Revoked by Admin')}
                        className="btn-secondary py-2 px-4 text-xs font-semibold text-amber-700 border-amber-200 hover:bg-amber-50"
                      >
                        Revoke Verification
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <section className="glass-card p-6 border-slate-200 space-y-4" aria-labelledby="audit-log-heading">
          <div className="flex flex-col gap-1 border-b border-slate-100 pb-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 id="audit-log-heading" className="font-bold text-lg text-slate-900 flex items-center gap-2">
              <History className="w-5 h-5 text-spandan-600" /> Recent System Activity
            </h3>
            <span className="text-xs font-semibold text-slate-500">Latest {auditLogs.length} audited events</span>
          </div>
          {auditLogs.length === 0 ? (
            <p className="py-5 text-center text-sm text-slate-500">No audited activity has been recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Time</th>
                    <th className="px-3 py-2 font-semibold">Action</th>
                    <th className="px-3 py-2 font-semibold">Entity</th>
                    <th className="px-3 py-2 font-semibold">Actor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {auditLogs.map((entry) => (
                    <tr key={entry.id} className="text-slate-700">
                      <td className="whitespace-nowrap px-3 py-3 text-xs">
                        {new Date(entry.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                      </td>
                      <td className="px-3 py-3 font-semibold text-slate-900">
                        {entry.action.replace(/[._]/g, ' ')}
                      </td>
                      <td className="px-3 py-3 text-xs">
                        {entry.entity_type}{entry.entity_id ? ` · ${entry.entity_id.slice(0, 8)}` : ''}
                      </td>
                      <td className="px-3 py-3 font-mono text-xs text-slate-500">
                        {entry.actor_user_id?.slice(0, 8) || 'system'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <Modal isOpen={!!rejectTarget} onClose={() => setRejectTarget(null)} title="Reject Doctor Verification">
          {rejectTarget && (
            <form onSubmit={handleConfirmReject} className="space-y-4">
              <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs">
                You are about to reject verification for <strong>{rejectTarget.full_name}</strong> (BMDC: {rejectTarget.medical_registration_number}).
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Rejection Notes / Discrepancy details
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. BMDC number expired or does not match council directory..."
                  value={rejectNotes}
                  onChange={(e) => setRejectNotes(e.target.value)}
                  className="input-field bg-white"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setRejectTarget(null)}
                  className="btn-secondary py-2 px-4 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rejectSubmitting}
                  className="btn-danger py-2 px-5 text-xs font-semibold"
                >
                  {rejectSubmitting ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          )}
        </Modal>
      </div>
    </DashboardLayout>
  );
};
