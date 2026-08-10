import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Activity, LogOut, Search, Sparkles, User as UserIcon } from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const getDashboardPath = () => {
    if (!user) return '/login';
    switch (user.role) {
      case 'patient':
        return '/dashboard/patient';
      case 'doctor':
        return '/dashboard/doctor';
      case 'assistant':
        return '/dashboard/assistant';
      case 'administrator':
        return '/dashboard/admin';
      default:
        return '/';
    }
  };

  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200/80 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-spandan-600 to-spandan-400 flex items-center justify-center text-white shadow-md shadow-spandan-500/20 group-hover:scale-105 transition duration-200">
            <Activity className="w-6 h-6 animate-pulse" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-xl tracking-tight bg-gradient-to-r from-slate-900 via-spandan-800 to-spandan-600 bg-clip-text text-transparent">
              Spandan
            </span>
            <span className="text-[10px] font-medium tracking-widest text-spandan-600 -mt-1">
              Find Care. Book Easily
            </span>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-6 font-medium text-slate-600 text-sm">
          <Link to="/doctors" className="hover:text-spandan-600 transition flex items-center gap-1.5">
            <Search className="w-4 h-4 text-slate-400" />
            Find Doctors
          </Link>
          <Link
            to="/ai-triage"
            className="hover:text-spandan-600 transition flex items-center gap-1.5 bg-spandan-50 text-spandan-700 px-3 py-1 rounded-full border border-spandan-200"
          >
            <Sparkles className="w-4 h-4 text-spandan-500" />
            AI Symptom Checker
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-3">
              <Link
                to={getDashboardPath()}
                className="btn-secondary text-sm py-2 px-4 shadow-none border-spandan-200 bg-spandan-50/50 hover:bg-spandan-100/50 text-spandan-800"
              >
                <UserIcon className="w-4 h-4" />
                <span className="hidden sm:inline">{user.full_name?.split(' ')[0] || 'Dashboard'}</span>
                <span className="text-xs bg-spandan-200 text-spandan-900 px-1.5 py-0.5 rounded uppercase font-semibold">
                  {user.role}
                </span>
              </Link>
              <button
                onClick={handleLogout}
                title="Logout"
                className="p-2 rounded-xl text-slate-500 hover:text-red-600 hover:bg-red-50 transition"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link to="/login" className="btn-secondary text-sm py-2 px-4">
                Login
              </Link>
              <Link to="/register" className="btn-primary text-sm py-2 px-4">
                Register
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
