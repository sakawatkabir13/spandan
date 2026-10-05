import { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useLanguage } from '../../context/LanguageContext';

export function EmailOTPField({ email, code, onChange, disabled = false }: {
  email: string; code: string; onChange: (code: string) => void; disabled?: boolean;
}) {
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [sentTo, setSentTo] = useState('');
  const [retryAt, setRetryAt] = useState(0);
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setRemaining(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000))), 1000);
    return () => window.clearInterval(timer);
  }, [retryAt]);
  const matches = Boolean(sentTo) && sentTo === email.trim().toLowerCase();
  return <div className="space-y-2 rounded-xl border border-spandan-200 p-4 bg-spandan-50/40">
    <p className="text-sm text-slate-600">{t('Verify your email before creating an account. Codes are sent from community.cuetinsights@gmail.com and expire in 10 minutes.')}</p>
    <button type="button" className="btn-secondary w-full" disabled={disabled || busy || remaining > 0 || !email.trim()} onClick={async event => {
      const form = event.currentTarget.closest('form');
      const input = form?.querySelector<HTMLInputElement>('input[type="email"]');
      if (input && !input.reportValidity()) return;
      setBusy(true); setMessage('');
      const target = email.trim().toLowerCase();
      try {
        const r = await apiClient.post('/auth/registration-code', { email: target });
        setSentTo(target); onChange(''); setMessage(r.data.message);
        setRetryAt(Date.now() + 60000); setRemaining(60);
      } catch (error) { setMessage(errorMessage(error)); }
      finally { setBusy(false); }
    }}>{busy ? t('Sending code…') : remaining > 0 ? `${t('Resend code in')} ${remaining}s` : t(matches ? 'Resend verification code' : 'Send verification code')}</button>
    {message && <p role="status" className="text-sm text-slate-700">{message}</p>}
    <label className="block text-sm font-medium">{t('Email verification code')}
      <input aria-label="Email verification code" name="email_otp" className="input-field mt-1" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} placeholder="000000" required value={code} disabled={disabled} onChange={event => onChange(event.target.value.replace(/\D/g, '').slice(0, 6))} />
    </label>
  </div>;
}
