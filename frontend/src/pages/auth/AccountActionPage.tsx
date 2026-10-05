import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MainLayout } from '../../components/layout/MainLayout';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';

export function AccountActionPage() {
  const [params] = useSearchParams();
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const purpose = params.get('purpose');
  const [done, setDone] = useState(false);
  return <MainLayout><section className="glass-card max-w-lg mx-auto p-6 space-y-4">
    <h1 className="text-2xl font-bold">{purpose ? 'Complete account verification' : 'Recover your account'}</h1>
    <p className="text-slate-600">Security links expire after 15 minutes. Contact community.cuetinsights@gmail.com if delivery is unavailable.</p>
    {message && <p role="status">{message}</p>}
    {!done && <form className="space-y-4" onSubmit={async event => {
      event.preventDefault(); setBusy(true);
      const fields = Object.fromEntries(new FormData(event.currentTarget));
      try {
        const r = purpose
          ? await apiClient.post('/auth/account-action', { ...fields, purpose, token: params.get('token') || fields.token })
          : await apiClient.post('/auth/forgot-password', fields);
        setMessage(r.data.message); setDone(true);
      } catch (error) { setMessage(errorMessage(error)); }
      finally { setBusy(false); }
    }}>
      <label className="block">Email<input aria-label="Email" name="email" type="email" autoComplete="email" required defaultValue={params.get('email') || ''} className="input-field" /></label>
      {purpose === 'phone' && <label className="block">Verification code<input name="token" inputMode="numeric" minLength={6} maxLength={6} required className="input-field" /></label>}
      {purpose === 'reset' && <label className="block">New password<input name="new_password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required className="input-field" /></label>}
      <button disabled={busy} className="btn-primary">{busy ? 'Working…' : purpose ? 'Confirm' : 'Send recovery link'}</button>
    </form>}
    <Link to="/login" className="underline">Back to sign in</Link>
  </section></MainLayout>;
}
