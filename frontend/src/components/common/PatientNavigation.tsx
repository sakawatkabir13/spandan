import { CalendarDays, FileHeart, Home, Stethoscope, UserRound } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';

export function PatientNavigation() {
  const { t: uiText } = useLanguage();
  const { user } = useAuth();
  const { pathname } = useLocation();
  const { t } = useLanguage();
  if (user?.role !== 'patient') return null;
  const items = [
    { label: 'Home', path: '/dashboard/patient/home', icon: Home, active: pathname.endsWith('/home') },
    { label: 'Doctors', path: '/doctors?view=booking', icon: Stethoscope, active: pathname.startsWith('/doctors') || pathname.startsWith('/directory') },
    { label: 'Visits', path: '/dashboard/patient', icon: CalendarDays, active: pathname === '/dashboard/patient' || pathname.includes('/appointments/') || pathname.endsWith('/payments') },
    { label: 'Records', path: '/dashboard/patient/records', icon: FileHeart, active: pathname.endsWith('/records') },
    { label: 'Account', path: '/dashboard/patient/profile', icon: UserRound, active: pathname.endsWith('/profile') || pathname.includes('/tools') },
  ];
  return <nav aria-label={uiText("Patient quick navigation")} className="mobile-nav fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur-lg lg:hidden"><div className="mx-auto grid max-w-lg grid-cols-5">{items.map(item => <Link key={item.path} to={item.path} aria-current={item.active ? 'page' : undefined} className={`flex flex-col items-center justify-center gap-1 px-1 text-[11px] font-semibold ${item.active ? 'text-spandan-700' : 'text-slate-500'}`}><item.icon className="h-5 w-5" strokeWidth={item.active ? 2.2 : 1.7} /><span>{t(item.label)}</span></Link>)}</div></nav>;
}
