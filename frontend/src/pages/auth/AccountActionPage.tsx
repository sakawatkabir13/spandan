import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MainLayout } from '../../components/layout/MainLayout';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useLanguage } from '../../context/LanguageContext';
import { useAuth } from '../../context/AuthContext';

export function AccountActionPage() {
  const { t } = useLanguage();
  const { user, logout } = useAuth();
  const [params] = useSearchParams();
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const purpose = params.get('purpose');
  const recovery = !purpose || purpose === 'reset';
  const [sent, setSent] = useState(purpose === 'reset');
  const [email, setEmail] = useState(params.get('email') || '');
  const [code, setCode] = useState('');
  const [retryAt, setRetryAt] = useState(0);
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setRemaining(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000))), 1000);
    return () => window.clearInterval(timer);
  }, [retryAt]);
  const requestCode = async () => {
    setBusy(true); setMessage('');
    try {
      const r = await apiClient.post('/auth/forgot-password', { email });
      setMessage(r.data.message); setSent(true); setCode('');
      setRetryAt(Date.now() + 60000); setRemaining(60);
    } catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(false); }
  };
  return <MainLayout><section className="glass-card max-w-lg mx-auto p-6 space-y-4">
    <h1 className="text-2xl font-bold">{t(recovery ? 'Reset your password' : 'Complete account verification')}</h1>
    <p className="text-slate-600">{t(recovery ? 'We will send a six-digit code from community.cuetinsights@gmail.com to your account email. The code expires in 10 minutes.' : 'Security links expire after 15 minutes.')}</p>
    {message && <p role="status">{message}</p>}
    {!done && <form className="space-y-4" onSubmit={async event => {
      event.preventDefault();
      if (recovery && !sent) { await requestCode(); return; }
      const fields = Object.fromEntries(new FormData(event.currentTarget));
      if (recovery && fields.new_password !== fields.confirm_password) { setMessage(t('Passwords do not match.')); return; }
      setBusy(true); setMessage('');
      try {
        const r = await apiClient.post('/auth/account-action', { email, purpose: recovery ? 'reset' : purpose, token: recovery ? code : params.get('token') || fields.token, new_password: fields.new_password });
        if (recovery && user?.email.toLowerCase() === email.trim().toLowerCase()) await logout(false);
        setMessage(recovery ? t('Password reset successfully. Sign in with your new password.') : r.data.message); setDone(true);
      } catch (error) { setMessage(errorMessage(error)); }
      finally { setBusy(false); }
    }}>
      <label className="block">{t('Email Address')}<input aria-label="Email" name="email" type="email" autoComplete="email" required readOnly={recovery && sent} value={email} onChange={event => setEmail(event.target.value)} className="input-field" /></label>
      {recovery && sent && <>
        <label className="block">{t('Email verification code')}<input aria-label="Email verification code" name="token" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required value={code} onChange={event => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} className="input-field" /></label>
        <label className="block">{t('New password')}<input aria-label="New password" name="new_password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required className="input-field" /></label>
        <label className="block">{t('Confirm new password')}<input aria-label="Confirm new password" name="confirm_password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required className="input-field" /></label>
        <p className="text-sm text-slate-600">{t('Use at least 12 characters. Resetting your password signs out all existing sessions.')}</p>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-secondary" disabled={busy || remaining > 0} onClick={() => void requestCode()}>{remaining > 0 ? `${t('Resend code in')} ${remaining}s` : t('Resend reset code')}</button>
          <button type="button" className="underline text-sm" disabled={busy} onClick={() => { setSent(false); setCode(''); setMessage(''); }}>{t('Change email')}</button>
        </div>
      </>}
      {purpose === 'phone' && <label className="block">{t('Verification code')}<input name="token" inputMode="numeric" minLength={6} maxLength={6} required className="input-field" /></label>}
      <button disabled={busy} className="btn-primary">{t(busy ? 'Working…' : recovery ? sent ? 'Reset password' : 'Send reset code' : 'Confirm')}</button>
    </form>}
    <Link to="/login" className="underline">{t('Back to sign in')}</Link>
  </section></MainLayout>;
}
