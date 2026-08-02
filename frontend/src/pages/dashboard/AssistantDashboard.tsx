import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ApiResponse, Schedule } from '../../types';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { Badge } from '../../components/common/Badge';
import { Calendar, Clock, MapPin } from 'lucide-react';

export const AssistantDashboard: React.FC = () => {
  useAuth();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSchedules = async () => {
      try {
        const resp = await apiClient.get<ApiResponse<Schedule[]>>('/schedules/me');
        if (resp.data.success) {
          setSchedules(resp.data.data);
        }
      } catch (err) {
        // ignore
      } finally {
        setLoading(false);
      }
    };
    fetchSchedules();
  }, []);

  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div className="glass-card p-6 border-slate-200">
          <h1 className="text-2xl font-bold text-slate-900">Assistant Queue Console</h1>
          <p className="text-sm text-slate-600">
            Manage live running serials, delays, and patient check-ins for your assigned doctor chambers.
          </p>
        </div>

        {loading ? (
          <LoadingSpinner size="lg" text="Loading assigned chamber schedules..." />
        ) : schedules.length === 0 ? (
          <div className="glass-card p-12 text-center text-slate-500">
            No open schedules found for your assigned chambers today.
          </div>
        ) : (
          <div className="glass-card p-6 border-slate-200 space-y-4">
            <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-spandan-600" /> Assigned Sessions
            </h3>

            <div className="space-y-4">
              {schedules.map((sched) => (
                <div
                  key={sched.id}
                  className="border border-slate-200 rounded-2xl p-5 bg-white flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">
                        {new Date(sched.schedule_date).toLocaleDateString('en-GB')}
                      </span>
                      <Badge variant="success">{sched.status.toUpperCase()}</Badge>
                    </div>
                    <p className="text-xs font-semibold text-spandan-700 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" />
                      {sched.chamber?.name} ({sched.chamber?.area})
                    </p>
                    <p className="text-xs text-slate-500 flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {sched.start_time.slice(0, 5)} - {sched.end_time.slice(0, 5)} | Running Serial #{sched.queue_state?.current_serial || 1}
                    </p>
                  </div>

                  <Link
                    to={`/dashboard/doctor/queue?schedule_id=${sched.id}`}
                    className="btn-primary py-2.5 px-5 text-xs font-semibold"
                  >
                    Open Live Queue Console
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};
