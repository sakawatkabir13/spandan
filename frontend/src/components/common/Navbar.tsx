import { I18nText } from '../../context/LanguageContext';
import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Activity, LogOut, Search, Sparkles, User as UserIcon } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

export const Navbar: React.FC = () => {
  const { t: uiText } = useLanguage();
  const { language, setLanguage, t } = useLanguage();
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const handleLogout = async () => {
    await logout();
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
    <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-xl shadow-[0_1px_12px_-6px_#0f172a20] border-b border-slate-200/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group shrink-0">
          <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-spandan-700 via-spandan-600 to-spandan-400 flex items-center justify-center text-white shadow-md shadow-spandan-500/20 group-hover:scale-105 transition duration-200">
            <Activity className="w-6 h-6" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-base sm:text-xl tracking-tight bg-gradient-to-r from-slate-900 via-spandan-800 to-spandan-600 bg-clip-text text-transparent">
               <I18nText text={"Spandan"} /> </span>
            <span className="hidden sm:block text-[10px] font-medium tracking-widest text-spandan-600 -mt-1">
               <I18nText text={"Find Care. Book Easily"} /> </span>
          </div>
        </Link>

        <nav className="hidden lg:flex items-center gap-6 font-medium text-slate-600 text-sm">
          <Link to="/doctors" aria-current={pathname.startsWith('/doctors') || pathname.startsWith('/directory') ? 'page' : undefined} className="navbar-link hover:text-spandan-600 transition flex items-center gap-1.5">
            <Search className="w-4 h-4 text-slate-400" />
            {t('Find Doctors')}
          </Link>
          <Link
            to="/ai-triage"
            aria-current={pathname === '/ai-triage' ? 'page' : undefined}
            className="navbar-link hover:text-spandan-600 transition flex items-center gap-1.5 bg-spandan-50 text-spandan-700 px-3 py-1 rounded-full border border-spandan-200"
          >
            <Sparkles className="w-4 h-4 text-spandan-500" />
            {t('AI Symptom Checker')}
          </Link>
        </nav>

        <div className="flex items-center gap-1 sm:gap-3">
          <button aria-label={uiText("Change language")} className="min-h-11 px-1 text-xs sm:text-sm font-semibold" onClick={() => setLanguage(language === 'en' ? 'bn' : 'en')}>{language === 'en' ? 'বাংলা' : 'English'}</button>
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2 sm:gap-3">
              <Link
                to={getDashboardPath()}
                aria-label={uiText("Open your dashboard")}
                className="btn-secondary text-sm py-2 px-2 sm:px-4 shadow-none border-spandan-200 bg-spandan-50/50 hover:bg-spandan-100/50 text-spandan-800"
              >
                <UserIcon className="w-4 h-4" />
                <span className="hidden sm:inline max-w-24 truncate">{user.full_name?.split(' ')[0] || 'Dashboard'}</span>
                <span className="hidden md:inline text-xs bg-spandan-200 text-spandan-900 px-1.5 py-0.5 rounded uppercase font-semibold">
                  {user.role}
                </span>
              </Link>
              <button
                onClick={handleLogout}
                title={uiText("Logout")}
                aria-label={uiText("Logout")}
                className="p-3 rounded-xl text-slate-500 hover:text-red-600 hover:bg-red-50 transition"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1 sm:gap-2">
              <Link to="/login" className="btn-secondary text-xs sm:text-sm py-2 px-2 sm:px-4">
                {t('Login')}
              </Link>
              <Link to="/register" className="btn-primary text-xs sm:text-sm py-2 px-2 sm:px-4">
                {t('Register')}
              </Link>
            </div>
          )}
        </div>
      </div>
      {!pathname.startsWith('/dashboard') && <nav aria-label={uiText("Mobile navigation")} className="lg:hidden flex flex-wrap gap-x-5 gap-y-2 px-4 pb-3 text-sm font-medium text-slate-600"><Link to="/doctors">{t('Find Doctors')}</Link><Link to="/ai-triage">{t('AI Symptom Checker')}</Link></nav>}
    </header>
  );
};
