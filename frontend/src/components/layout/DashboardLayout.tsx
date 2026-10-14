import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Navbar } from '../common/Navbar';
import { Footer } from '../common/Footer';
import { Activity, Bell, Calendar, ChevronDown, Clock, CreditCard, FileHeart, MapPin, Settings, Sparkles, Stethoscope, User as UserIcon, Users } from 'lucide-react';

export const DashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => setMenuOpen(false), [location.pathname, location.search, location.hash]);
  if (!user) return null;
  const role = user.role === 'administrator' ? 'admin' : user.role;
  const links = user.role === 'patient' ? [
    { name: 'My appointments', path: '/dashboard/patient', icon: Calendar },
    { name: 'Payments & receipts', path: '/dashboard/patient/payments', icon: CreditCard },
    { name: 'My profile & records', path: '/dashboard/patient/profile', icon: FileHeart },
    { name: 'Find doctors', path: '/doctors', icon: Stethoscope },
    { name: 'AI symptom checker', path: '/ai-triage', icon: Sparkles },
    { name: 'Notifications', path: '/dashboard/patient/tools?tab=notifications', icon: Bell },
    { name: 'Account settings', path: '/dashboard/patient/tools?tab=security', icon: Settings },
  ] : [
    ...(user.role === 'doctor' ? [
      { name: 'Chambers & schedules', path: '/dashboard/doctor', icon: Calendar },
      { name: 'Live queue console', path: '/dashboard/doctor/queue', icon: Clock },
      { name: 'My chambers', path: '/dashboard/doctor/chambers', icon: MapPin },
      { name: 'Doctor profile & BMDC', path: '/dashboard/doctor/profile', icon: Stethoscope },
    ] : user.role === 'assistant' ? [
      { name: 'Assigned chambers', path: '/dashboard/assistant', icon: MapPin },
      { name: 'Queue management', path: '/dashboard/assistant/queue', icon: Clock },
      { name: 'My profile', path: '/dashboard/assistant/profile', icon: UserIcon },
    ] : [
      { name: 'System overview', path: '/dashboard/admin', icon: Activity },
      { name: 'Doctor verification', path: '/dashboard/admin/verifications', icon: Stethoscope },
      { name: 'User management', path: '/dashboard/admin/users', icon: Users },
      { name: 'My profile', path: '/dashboard/admin/profile', icon: UserIcon },
    ]),
    { name: 'Account & chamber tools', path: `/dashboard/${role}/tools`, icon: Settings },
  ];
  const active = (path: string) => {
    const [pathname, search] = path.split('?');
    if (location.pathname !== pathname) return false;
    if (search) return new URLSearchParams(search).get('tab') === (new URLSearchParams(location.search).get('tab') || 'notifications');
    return !pathname.endsWith('/tools') || (new URLSearchParams(location.search).get('tab') || 'notifications') !== 'notifications';
  };
  const mobileLinks = [
    { name: 'Appointments', path: '/dashboard/patient', icon: Calendar },
    { name: 'Payments', path: '/dashboard/patient/payments', icon: CreditCard },
    { name: 'Find doctors', path: '/doctors', icon: Stethoscope },
    { name: 'Profile', path: '/dashboard/patient/profile', icon: UserIcon },
  ];
  return <div className={`min-h-screen flex flex-col bg-slate-50 ${user.role === 'patient' ? 'pb-20 lg:pb-0' : ''}`}>
    <Navbar />
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5 sm:py-8 flex flex-col lg:flex-row gap-5 lg:gap-7">
      <aside className="w-full lg:w-60 shrink-0">
        <div className="glass-card p-3 lg:p-4 lg:sticky lg:top-24">
          <button type="button" aria-expanded={menuOpen} aria-controls="dashboard-navigation" onClick={() => setMenuOpen(!menuOpen)} className="lg:hidden w-full flex items-center justify-between gap-3 p-1 text-sm font-semibold">
            <span className="flex min-w-0 items-center gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-spandan-100 text-spandan-800">{user.full_name?.charAt(0) || 'U'}</span><span className="truncate">{user.full_name || 'My account'}</span></span>
            <span className="flex shrink-0 items-center gap-1 text-slate-500">Menu<ChevronDown className={`h-4 w-4 transition ${menuOpen ? 'rotate-180' : ''}`} /></span>
          </button>
          <div className="hidden lg:flex items-center gap-3 border-b border-slate-100 px-2 pb-4 mb-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-spandan-100 text-spandan-800 font-bold">{user.full_name?.charAt(0) || 'U'}</span>
            <div className="min-w-0"><p className="font-semibold text-sm truncate">{user.full_name || 'Spandan user'}</p><p className="text-xs text-slate-500 capitalize">{user.role}</p></div>
          </div>
          <nav id="dashboard-navigation" aria-label="Dashboard navigation" className={`${menuOpen ? 'block mt-3' : 'hidden'} lg:block space-y-1`}>
            {links.map(link => <Link key={link.path} to={link.path} aria-current={active(link.path) ? 'page' : undefined} className={`flex min-w-0 items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition ${active(link.path) ? 'bg-spandan-600 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}><link.icon className="h-4 w-4 shrink-0" /><span>{link.name}</span></Link>)}
          </nav>
        </div>
      </aside>
      <main id="main-content" tabIndex={-1} className="dashboard-content flex-1 min-w-0 animate-fade-in">{children}</main>
    </div>
    <Footer compact />
    {user.role === 'patient' && <nav aria-label="Patient quick navigation" className="fixed bottom-0 inset-x-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur-md lg:hidden safe-bottom"><div className="grid grid-cols-4 max-w-lg mx-auto">{mobileLinks.map(link => <Link key={link.path} to={link.path} aria-current={active(link.path) ? 'page' : undefined} className={`flex min-w-0 flex-col items-center gap-1 px-1 py-3 text-[11px] font-semibold ${active(link.path) ? 'text-spandan-700 bg-spandan-50' : 'text-slate-500'}`}><link.icon className="h-5 w-5" /><span>{link.name}</span></Link>)}</div></nav>}
  </div>;
};
