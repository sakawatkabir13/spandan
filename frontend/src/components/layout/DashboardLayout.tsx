import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Navbar } from '../common/Navbar';
import { Footer } from '../common/Footer';
import {
  Activity,
  Calendar,
  Clock,
  MapPin,
  Sparkles,
  Stethoscope,
  User as UserIcon,
  Users,
} from 'lucide-react';

export const DashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) return null;

  const getSidebarLinks = () => {
    switch (user.role) {
      case 'patient':
        return [
          { name: 'My Appointments', path: '/dashboard/patient', icon: Calendar },
          { name: 'Find Doctors', path: '/doctors', icon: Stethoscope },
          { name: 'AI Symptom Triage', path: '/ai-triage', icon: Sparkles },
          { name: 'My Profile', path: '/dashboard/patient/profile', icon: UserIcon },
        ];
      case 'doctor':
        return [
          { name: 'Chamber & Schedules', path: '/dashboard/doctor', icon: Calendar },
          { name: 'Live Queue Console', path: '/dashboard/doctor/queue', icon: Clock },
          { name: 'My Chambers', path: '/dashboard/doctor/chambers', icon: MapPin },
          { name: 'Doctor Profile & BMDC', path: '/dashboard/doctor/profile', icon: Stethoscope },
        ];
      case 'assistant':
        return [
          { name: 'Assigned Chambers', path: '/dashboard/assistant', icon: MapPin },
          { name: 'Queue Management', path: '/dashboard/assistant/queue', icon: Clock },
          { name: 'My Profile', path: '/dashboard/assistant/profile', icon: UserIcon },
        ];
      case 'administrator':
        return [
          { name: 'System Overview', path: '/dashboard/admin', icon: Activity },
          { name: 'Doctor BMDC Verification', path: '/dashboard/admin/verifications', icon: Stethoscope },
          { name: 'User Management', path: '/dashboard/admin/users', icon: Users },
          { name: 'My Profile', path: '/dashboard/admin/profile', icon: UserIcon },
        ];
      default:
        return [];
    }
  };

  const links = getSidebarLinks();

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar />
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col md:flex-row gap-8">
        {/* Sidebar */}
        <aside className="w-full md:w-64 flex-shrink-0">
          <div className="glass-card p-4 sticky top-24 space-y-2 border-slate-200/80">
            <div className="pb-3 mb-3 border-b border-slate-100 flex items-center gap-3 px-2">
              <div className="w-10 h-10 rounded-full bg-spandan-100 text-spandan-800 flex items-center justify-center font-bold text-lg">
                {user.full_name?.charAt(0) || 'U'}
              </div>
              <div className="overflow-hidden">
                <h3 className="font-semibold text-sm text-slate-800 truncate">{user.full_name || 'Spandan User'}</h3>
                <p className="text-xs text-spandan-600 font-medium uppercase tracking-wider">
                  {user.role}
                </p>
              </div>
            </div>

            <nav className="space-y-1">
              {links.map((link) => {
                const Icon = link.icon;
                const isActive = location.pathname === link.path;
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition duration-200 ${
                      isActive
                        ? 'bg-spandan-600 text-white shadow-md shadow-spandan-500/20 font-semibold'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`}
                  >
                    <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                    <span>{link.name}</span>
                  </Link>
                );
              })}
            </nav>
          </div>
        </aside>

        {/* Main Dashboard Area */}
        <div className="flex-1 min-w-0 animate-fade-in">{children}</div>
      </div>
      <Footer />
    </div>
  );
};
