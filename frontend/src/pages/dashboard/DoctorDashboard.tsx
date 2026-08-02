import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ApiResponse, Chamber, Schedule } from '../../types';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import {
  Calendar,
  Clock,
  MapPin,
  Plus,
} from 'lucide-react';

export const DoctorDashboard: React.FC = () => {
  useAuth();
  const [chambers, setChambers] = useState<Chamber[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);

  // Chamber Modal
  const [chamberModalOpen, setChamberModalOpen] = useState(false);
  const [chamName, setChamName] = useState('');
  const [chamAddress, setChamAddress] = useState('');
  const [chamArea, setChamArea] = useState('');
  const [chamDistrict, setChamDistrict] = useState('Dhaka');
  const [chamFee, setChamFee] = useState(1000);
  const [chamFollowup, setChamFollowup] = useState(600);
  const [chamPhone, setChamPhone] = useState('');
  const [chamSubmitting, setChamSubmitting] = useState(false);

  // Schedule Modal
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [schedChamberId, setSchedChamberId] = useState('');
  const [schedDate, setSchedDate] = useState('');
  const [schedStart, setSchedStart] = useState('17:00');
  const [schedEnd, setSchedEnd] = useState('21:00');
  const [schedMax, setSchedMax] = useState(30);
  const [schedMinsPerPatient, setSchedMinsPerPatient] = useState(10);
  const [schedSubmitting, setSchedSubmitting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [cResp, sResp] = await Promise.all([
        apiClient.get<ApiResponse<Chamber[]>>('/chambers/me'),
        apiClient.get<ApiResponse<Schedule[]>>('/schedules/me'),
      ]);
      if (cResp.data.success) setChambers(cResp.data.data);
      if (sResp.data.success) setSchedules(sResp.data.data);
    } catch (err) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateChamber = async (e: React.FormEvent) => {
    e.preventDefault();
    setChamSubmitting(true);
    try {
      await apiClient.post('/chambers', {
        name: chamName,
        address: chamAddress,
        area: chamArea,
        district: chamDistrict,
        consultation_fee: Number(chamFee),
        follow_up_fee: Number(chamFollowup),
        phone_number: chamPhone || undefined,
      });
      setChamberModalOpen(false);
      setChamName('');
      setChamAddress('');
      setChamArea('');
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.error?.message || 'Failed to create chamber.');
    } finally {
      setChamSubmitting(false);
    }
  };

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!schedChamberId) {
      alert('Please select a chamber.');
      return;
    }
    setSchedSubmitting(true);
    try {
      await apiClient.post('/schedules', {
        chamber_id: schedChamberId,
        schedule_date: schedDate,
        start_time: `${schedStart}:00`,
        end_time: `${schedEnd}:00`,
        maximum_patients: Number(schedMax),
        estimated_minutes_per_patient: Number(schedMinsPerPatient),
      });
      setScheduleModalOpen(false);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.error?.message || 'Failed to create schedule.');
    } finally {
      setSchedSubmitting(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Header */}
        <div className="glass-card p-6 border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Doctor Chamber Portal</h1>
            <p className="text-sm text-slate-600">
              Manage your private consultation centers, schedules, and enter live queue operations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setChamberModalOpen(true)}
              className="btn-secondary py-2 px-4 text-xs font-semibold"
            >
              <Plus className="w-4 h-4" /> Add Chamber
            </button>
            <button
              onClick={() => {
                if (chambers.length === 0) {
                  alert('Please create at least one chamber before adding a schedule.');
                  return;
                }
                setSchedChamberId(chambers[0].id);
                setScheduleModalOpen(true);
              }}
              className="btn-primary py-2 px-4 text-xs font-semibold"
            >
              <Plus className="w-4 h-4" /> Add Schedule
            </button>
          </div>
        </div>

        {loading ? (
          <LoadingSpinner size="lg" text="Loading your chamber operations..." />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Schedules Column */}
            <div className="lg:col-span-2 space-y-6">
              <div className="glass-card p-6 border-slate-200 space-y-4">
                <div className="flex items-center justify-between border-b pb-3">
                  <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-spandan-600" /> Active & Upcoming Schedules
                  </h3>
                  <span className="text-xs text-slate-500 font-semibold">{schedules.length} Sessions</span>
                </div>

                {schedules.length === 0 ? (
                  <p className="text-sm text-slate-500 py-6 text-center italic">
                    No consultation sessions listed. Click "Add Schedule" above to create one.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {schedules.map((sched) => {
                      const chamber = chambers.find((c) => c.id === sched.chamber_id) || sched.chamber;
                      return (
                        <div
                          key={sched.id}
                          className="border border-slate-200 rounded-2xl p-5 bg-white/60 hover:bg-white transition flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
                        >
                          <div className="space-y-1.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-base text-slate-900">
                                {new Date(sched.schedule_date).toLocaleDateString('en-GB', {
                                  weekday: 'short',
                                  day: 'numeric',
                                  month: 'short',
                                  year: 'numeric',
                                })}
                              </span>
                              <Badge variant={sched.status === 'open' ? 'success' : 'warning'}>
                                {sched.status.toUpperCase()}
                              </Badge>
                            </div>

                            <p className="text-xs font-semibold text-spandan-700 flex items-center gap-1.5">
                              <MapPin className="w-3.5 h-3.5" />
                              {chamber ? `${chamber.name} (${chamber.area})` : 'Private Chamber'}
                            </p>

                            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3.5 h-3.5 text-slate-400" />
                                {sched.start_time.slice(0, 5)} - {sched.end_time.slice(0, 5)}
                              </span>
                              <span>
                                Max Capacity: <strong>{sched.maximum_patients}</strong>
                              </span>
                            </div>

                            {sched.queue_state && (
                              <div className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg inline-block font-semibold mt-1">
                                Live Console: Serial #{sched.queue_state.current_serial}{' '}
                                {sched.queue_state.delay_minutes > 0 && `(+${sched.queue_state.delay_minutes}m delay)`}
                              </div>
                            )}
                          </div>

                          <div className="flex sm:flex-col items-center sm:items-end gap-2 w-full sm:w-auto">
                            <Link
                              to={`/dashboard/doctor/queue?schedule_id=${sched.id}`}
                              className="btn-primary py-2.5 px-5 text-xs font-semibold whitespace-nowrap w-full sm:w-auto text-center"
                            >
                              Launch Queue Console
                            </Link>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Chambers Sidebar */}
            <div className="space-y-6">
              <div className="glass-card p-6 border-slate-200 space-y-4">
                <div className="flex items-center justify-between border-b pb-3">
                  <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-spandan-600" /> My Chambers
                  </h3>
                  <span className="text-xs text-slate-500 font-semibold">{chambers.length} Locations</span>
                </div>

                {chambers.length === 0 ? (
                  <p className="text-xs text-slate-500 py-4 text-center">No chambers added yet.</p>
                ) : (
                  <div className="space-y-4">
                    {chambers.map((c) => (
                      <div key={c.id} className="p-4 rounded-xl bg-slate-50/80 border border-slate-200/80 space-y-1.5">
                        <h4 className="font-bold text-sm text-slate-900">{c.name}</h4>
                        <p className="text-xs text-slate-600">{c.address}</p>
                        <p className="text-xs text-slate-500">
                          {c.area}, {c.district}
                        </p>
                        <div className="flex justify-between text-xs font-semibold pt-1 text-spandan-800">
                          <span>New Fee: ৳{c.consultation_fee}</span>
                          {c.follow_up_fee && <span>Follow-up: ৳{c.follow_up_fee}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Add Chamber Modal */}
        <Modal isOpen={chamberModalOpen} onClose={() => setChamberModalOpen(false)} title="Register New Chamber">
          <form onSubmit={handleCreateChamber} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                Chamber / Center Name
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Popular Diagnostic Dhanmondi / Labaid Specialist"
                value={chamName}
                onChange={(e) => setChamName(e.target.value)}
                className="input-field bg-white"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Area / Thana</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Dhanmondi / Mirpur / Gulshan"
                  value={chamArea}
                  onChange={(e) => setChamArea(e.target.value)}
                  className="input-field bg-white"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">District / City</label>
                <input
                  type="text"
                  required
                  value={chamDistrict}
                  onChange={(e) => setChamDistrict(e.target.value)}
                  className="input-field bg-white"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Street Address</label>
              <input
                type="text"
                required
                placeholder="e.g. House #16, Road #2, Dhanmondi R/A"
                value={chamAddress}
                onChange={(e) => setChamAddress(e.target.value)}
                className="input-field bg-white"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Consultation Fee (৳)
                </label>
                <input
                  type="number"
                  required
                  min={100}
                  step={50}
                  value={chamFee}
                  onChange={(e) => setChamFee(Number(e.target.value))}
                  className="input-field bg-white"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Follow-up Fee (৳)
                </label>
                <input
                  type="number"
                  required
                  min={100}
                  step={50}
                  value={chamFollowup}
                  onChange={(e) => setChamFollowup(Number(e.target.value))}
                  className="input-field bg-white"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                Chamber Reception Phone (Optional)
              </label>
              <input
                type="text"
                placeholder="+8801712345678"
                value={chamPhone}
                onChange={(e) => setChamPhone(e.target.value)}
                className="input-field bg-white"
              />
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setChamberModalOpen(false)}
                className="btn-secondary py-2 px-4 text-xs font-semibold"
              >
                Cancel
              </button>
              <button type="submit" disabled={chamSubmitting} className="btn-primary py-2 px-5 text-xs font-semibold">
                {chamSubmitting ? 'Saving...' : 'Save Chamber'}
              </button>
            </div>
          </form>
        </Modal>

        {/* Add Schedule Modal */}
        <Modal isOpen={scheduleModalOpen} onClose={() => setScheduleModalOpen(false)} title="Create New Schedule">
          <form onSubmit={handleCreateSchedule} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Select Chamber</label>
              <select
                value={schedChamberId}
                onChange={(e) => setSchedChamberId(e.target.value)}
                className="input-field bg-white cursor-pointer"
              >
                {chambers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.area}) - ৳{c.consultation_fee}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Date</label>
              <input
                type="date"
                required
                value={schedDate}
                onChange={(e) => setSchedDate(e.target.value)}
                className="input-field bg-white"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Start Time</label>
                <input
                  type="time"
                  required
                  value={schedStart}
                  onChange={(e) => setSchedStart(e.target.value)}
                  className="input-field bg-white"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">End Time</label>
                <input
                  type="time"
                  required
                  value={schedEnd}
                  onChange={(e) => setSchedEnd(e.target.value)}
                  className="input-field bg-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Maximum Serials</label>
                <input
                  type="number"
                  required
                  min={1}
                  max={100}
                  value={schedMax}
                  onChange={(e) => setSchedMax(Number(e.target.value))}
                  className="input-field bg-white"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Avg. Mins Per Patient
                </label>
                <input
                  type="number"
                  required
                  min={3}
                  max={60}
                  value={schedMinsPerPatient}
                  onChange={(e) => setSchedMinsPerPatient(Number(e.target.value))}
                  className="input-field bg-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setScheduleModalOpen(false)}
                className="btn-secondary py-2 px-4 text-xs font-semibold"
              >
                Cancel
              </button>
              <button type="submit" disabled={schedSubmitting} className="btn-primary py-2 px-5 text-xs font-semibold">
                {schedSubmitting ? 'Creating...' : 'Create Schedule'}
              </button>
            </div>
          </form>
        </Modal>
      </div>
    </DashboardLayout>
  );
};
