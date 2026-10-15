import { I18nText } from '../../context/LanguageContext';
import { useLanguage } from '../../context/LanguageContext';
import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { MainLayout } from '../../components/layout/MainLayout';
import { Alert } from '../../components/common/Alert';
import { Activity, ArrowRight, Lock, Mail } from 'lucide-react';
import { errorMessage } from '../../api/errors';

export const LoginPage: React.FC = () => {
  const { t: uiText } = useLanguage();
  const { t } = useLanguage();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const initialRoleHint = queryParams.get('role');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const user = await login(email, password, mfaCode);
      const from = location.state?.from;
      if (typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') && (from.startsWith('/doctors/') || from.startsWith(`/dashboard/${user.role === 'administrator' ? 'admin' : user.role}`))) { navigate(from, { replace: true }); return; }
      if (user.role === 'patient') navigate('/dashboard/patient');
      else if (user.role === 'doctor') navigate('/dashboard/doctor');
      else if (user.role === 'assistant') navigate('/dashboard/assistant');
      else if (user.role === 'administrator') navigate('/dashboard/admin');
      else navigate('/');
    } catch (err: any) {
      const msg = errorMessage(err, 'Unable to sign in. Please try again.');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout compact>
      <div className="max-w-md mx-auto py-3 sm:py-8">
        <div className="glass-card p-5 sm:p-8 border-slate-200 shadow-xl space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-spandan-600 to-spandan-400 flex items-center justify-center text-white mx-auto shadow-md shadow-spandan-500/20">
              <Activity className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900">{t('Welcome back to Spandan')}</h1>
            <p className="text-sm text-slate-500">
              {initialRoleHint === 'doctor'
                ? 'Doctor Chamber Portal Login'
                : 'Sign in to your patient or chamber account'}
            </p>
          </div>

          {error && <Alert type="error" title={uiText("Login Failed")} message={error} onClose={() => setError(null)} />}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">{t('Email Address')}</label>
              <div className="field-with-icon">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input aria-label={uiText("Email Address")}
                  type="email"
                  autoComplete="email"
                  required
                  placeholder={uiText("you@example.com")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field pl-10"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">{t('Password')}</label>
              </div>
              <div className="field-with-icon">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input aria-label={uiText("Password")}
                  type="password"
                  autoComplete="current-password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pl-10"
                />
              </div>
            </div>

            <details className="rounded-xl border border-slate-200 p-3"><summary className="text-sm text-slate-600 font-medium"> <I18nText text={"Use an authenticator or recovery code"} /> </summary><label className="mt-3 block text-sm"> <I18nText text={"Authenticator or recovery code"} /> <input aria-label={uiText("Authenticator code")} value={mfaCode} onChange={e => setMfaCode(e.target.value)} autoComplete="one-time-code" maxLength={30} className="input-field mt-1" /></label><p className="mt-2 text-xs text-slate-500"> <I18nText text={"Use your six-digit authenticator code, or one unused recovery code."} /> </p></details>
            <Link to="/forgot-password" className="block underline text-sm">{t('Forgot your password?')}</Link>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 mt-2 font-semibold shadow-md"
            >
              {loading ? t('Signing in...') : t('Sign In')}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="pt-4 border-t border-slate-100 text-center text-sm text-slate-600 space-y-2">
            <p>
               <I18nText text={"Don't have an account yet?"} /> {' '}
              <Link to="/register" className="font-semibold text-spandan-600 hover:text-spandan-700 underline">
                 <I18nText text={"Register here"} /> </Link>
            </p>
          </div>
        </div>
      </div>
    </MainLayout>
  );
};
