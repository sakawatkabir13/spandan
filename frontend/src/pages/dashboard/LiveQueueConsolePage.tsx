import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ApiResponse, Appointment, Schedule } from '../../types';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import {
  Activity,
  ArrowRight,
  Clock,
  RefreshCw,
  Sliders,
  UserCheck,
} from 'lucide-react';

export const LiveQueueConsolePage: React.FC = () => {
  useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const queryParams = new URLSearchParams(location.search);
  const scheduleId = queryParams.get('schedule_id');

  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Queue Controls State
  const [delayMins, setDelayMins] = useState<number>(0);
  const [statusMsg, setStatusMsg] = useState<string>('');
  const [updatingQueue, setUpdatingQueue] = useState(false);

  const fetchQueueData = async () => {
    if (!scheduleId) return;
    try {
      const [sResp, aResp] = await Promise.all([
        apiClient.get<ApiResponse<Schedule>>(`/schedules/${scheduleId}`),
        apiClient.get<ApiResponse<Appointment[]>>(`/appointments/schedule/${scheduleId}`),
      ]);
      if (sResp.data.success) {
        setSchedule(sResp.data.data);
        if (sResp.data.data.queue_state) {
          setDelayMins(sResp.data.data.queue_state.delay_minutes);
          setStatusMsg(sResp.data.data.queue_state.status_message || '');
        }
      }
      if (aResp.data.success) {
        setAppointments(aResp.data.data);
      }
    } catch (err) {
      // ignore
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!scheduleId) {
      // if no schedule_id provided in query, fetch first open schedule for doctor
      const fetchFirstSchedule = async () => {
        try {
          const resp = await apiClient.get<ApiResponse<Schedule[]>>('/schedules/me');
          if (resp.data.success && resp.data.data.length > 0) {
            const first = resp.data.data[0];
            navigate(`/dashboard/doctor/queue?schedule_id=${first.id}`, { replace: true });
          } else {
            setLoading(false);
          }
        } catch (e) {
          setLoading(false);
        }
      };
      fetchFirstSchedule();
    } else {
      fetchQueueData();
    }
  }, [scheduleId]);

  const handleIncrementSerial = async () => {
    if (!scheduleId) return;
    setUpdatingQueue(true);
    try {
      await apiClient.post(`/schedules/${scheduleId}/queue/increment`);
      await fetchQueueData();
    } catch (err: any) {
      alert(err.response?.data?.error?.message || 'Failed to increment serial.');
    } finally {
      setUpdatingQueue(false);
    }
  };

  const handleUpdateDelayAndMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleId) return;
    setUpdatingQueue(true);
    try {
      await apiClient.patch(`/schedules/${scheduleId}/queue`, {
        delay_minutes: Number(delayMins),
        status_message: statusMsg || undefined,
      });
      await fetchQueueData();
      alert('Queue broadcast updated successfully.');
    } catch (err: any) {
      alert('Failed to update queue broadcast.');
    } finally {
      setUpdatingQueue(false);
    }
  };

  const handleUpdateStatus = async (appId: string, status: string) => {
    try {
      await apiClient.patch(`/appointments/${appId}/status`, {
        appointment_status: status,
      });
      fetchQueueData();
    } catch (err: any) {
      alert('Failed to update patient status.');
    }
  };

  if (loading) return <DashboardLayout><LoadingSpinner size="lg" text="Connecting to live chamber queue..." /></DashboardLayout>;
  if (!schedule) {
    return (
      <DashboardLayout>
        <div className="glass-card p-12 text-center space-y-4">
          <Clock className="w-12 h-12 text-slate-400 mx-auto" />
          <h3 className="font-bold text-lg text-slate-800">No active consultation session selected</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            Please select an open schedule from your schedules panel to start controlling the serial numbers.
          </p>
        </div>
      </DashboardLayout>
    );
  }

  const queue = schedule.queue_state;

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Header Banner */}
        <div className="bg-gradient-to-r from-slate-900 via-spandan-950 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border border-slate-800">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 animate-pulse">
                <Activity className="w-3.5 h-3.5" /> LIVE CHAMBER CONSOLE
              </span>
              <span className="text-xs text-slate-400">
                Date: {new Date(schedule.schedule_date).toLocaleDateString('en-GB')}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              {schedule.chamber?.name || 'Private Consultation Chamber'}
            </h1>
            <p className="text-xs text-slate-300">
              Session Hours: {schedule.start_time.slice(0, 5)} - {schedule.end_time.slice(0, 5)} | Capacity: {schedule.booked_count ?? appointments.length} / {schedule.maximum_patients} booked
            </p>
          </div>

          <div className="flex items-center gap-4 bg-white/10 backdrop-blur-md p-4 rounded-2xl border border-white/20 w-full md:w-auto justify-around">
            <div className="text-center">
              <span className="text-[11px] uppercase tracking-wider text-slate-300 font-semibold block">
                Running Serial
              </span>
              <span className="text-4xl font-black text-emerald-400">
                #{queue?.current_serial || 1}
              </span>
            </div>

            <button
              onClick={handleIncrementSerial}
              disabled={updatingQueue}
              className="btn-primary py-3 px-6 text-sm font-bold shadow-lg shadow-spandan-500/40"
            >
              Call Next (#{(queue?.current_serial || 1) + 1})
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Queue Broadcast Settings & Delay Adjuster */}
        <div className="glass-card p-6 border-slate-200">
          <form onSubmit={handleUpdateDelayAndMessage} className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
            <div className="md:col-span-3">
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-600" /> Chamber Delay (Mins)
              </label>
              <input
                type="number"
                min={0}
                max={300}
                step={5}
                value={delayMins}
                onChange={(e) => setDelayMins(Number(e.target.value))}
                className="input-field bg-white"
              />
            </div>

            <div className="md:col-span-7">
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-spandan-600" /> Live Status Broadcast Message
              </label>
              <input
                type="text"
                placeholder="e.g. Doctor is in chamber; running smoothly or 20 mins delayed due to surgery..."
                value={statusMsg}
                onChange={(e) => setStatusMsg(e.target.value)}
                className="input-field bg-white"
              />
            </div>

            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={updatingQueue}
                className="btn-secondary w-full py-2.5 text-xs font-semibold"
              >
                Broadcast Update
              </button>
            </div>
          </form>
        </div>

        {/* Booked Patient Roster */}
        <div className="glass-card p-6 border-slate-200 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-spandan-600" /> Booked Patient Roster ({appointments.length})
            </h3>
            <button
              onClick={() => {
                setRefreshing(true);
                fetchQueueData();
              }}
              className="p-2 rounded-xl text-slate-500 hover:text-spandan-600 hover:bg-slate-100 transition text-xs flex items-center gap-1"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
            </button>
          </div>

          {appointments.length === 0 ? (
            <p className="text-sm text-slate-500 py-8 text-center italic">
              No patients booked for this schedule yet.
            </p>
          ) : (
            <div className="divide-y divide-slate-100">
              {appointments.map((app) => {
                const isCurrent = queue?.current_serial === app.serial_number;
                const status = app.appointment_status;

                return (
                  <div
                    key={app.id}
                    className={`py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition ${
                      isCurrent ? 'bg-spandan-50/80 -mx-4 px-4 rounded-2xl border border-spandan-200/80 my-1' : ''
                    }`}
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={`w-12 h-12 rounded-xl flex items-center justify-center font-extrabold text-base flex-shrink-0 ${
                          isCurrent
                            ? 'bg-spandan-600 text-white shadow-md shadow-spandan-500/30'
                            : status === 'completed'
                            ? 'bg-slate-200 text-slate-500'
                            : 'bg-slate-100 text-slate-800'
                        }`}
                      >
                        #{app.serial_number}
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center gap-2.5">
                          <h4 className="font-bold text-sm sm:text-base text-slate-900">
                            {app.patient?.user?.full_name || 'Patient Name'}
                          </h4>
                          <Badge
                            variant={
                              status === 'in_consultation'
                                ? 'primary'
                                : status === 'checked_in'
                                ? 'info'
                                : status === 'completed'
                                ? 'neutral'
                                : status === 'cancelled'
                                ? 'danger'
                                : 'success'
                            }
                          >
                            {status.replace('_', ' ').toUpperCase()}
                          </Badge>
                          {isCurrent && (
                            <span className="text-[10px] bg-spandan-600 text-white px-2 py-0.5 rounded-full font-bold uppercase tracking-wide animate-pulse">
                              Inside Chamber
                            </span>
                          )}
                        </div>

                        <p className="text-xs text-slate-500">
                          Phone: <strong className="text-slate-700">{app.patient?.user?.phone_number}</strong> | Booked via {app.booking_source}
                        </p>
                        {app.patient_note && (
                          <p className="text-xs text-amber-800 bg-amber-50 px-2 py-1 rounded italic max-w-lg">
                            Note: "{app.patient_note}"
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    {status !== 'cancelled' && status !== 'completed' && (
                      <div className="flex flex-wrap items-center gap-2 self-end sm:self-center">
                        {status !== 'checked_in' && status !== 'in_consultation' && (
                          <button
                            onClick={() => handleUpdateStatus(app.id, 'checked_in')}
                            className="btn-secondary py-1.5 px-3 text-xs font-semibold bg-blue-50 text-blue-800 border-blue-200 hover:bg-blue-100"
                          >
                            Check-In
                          </button>
                        )}
                        {status !== 'in_consultation' && (
                          <button
                            onClick={() => handleUpdateStatus(app.id, 'in_consultation')}
                            className="btn-secondary py-1.5 px-3 text-xs font-semibold bg-spandan-50 text-spandan-800 border-spandan-200 hover:bg-spandan-100"
                          >
                            In Room
                          </button>
                        )}
                        <button
                          onClick={() => handleUpdateStatus(app.id, 'completed')}
                          className="btn-primary py-1.5 px-3 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 shadow-none"
                        >
                          Complete
                        </button>
                        <button
                          onClick={() => handleUpdateStatus(app.id, 'no_show')}
                          className="btn-secondary py-1.5 px-3 text-xs font-semibold text-red-600 border-red-200 hover:bg-red-50"
                        >
                          No-Show
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
};
