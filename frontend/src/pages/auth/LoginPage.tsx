import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { MainLayout } from '../../components/layout/MainLayout';
import { Alert } from '../../components/common/Alert';
import { Activity, ArrowRight, Lock, Mail } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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
      const user = await login(email, password);
      if (user.role === 'patient') navigate('/dashboard/patient');
      else if (user.role === 'doctor') navigate('/dashboard/doctor');
      else if (user.role === 'assistant') navigate('/dashboard/assistant');
      else if (user.role === 'administrator') navigate('/dashboard/admin');
      else navigate('/');
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Invalid email or password. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="max-w-md mx-auto py-8">
        <div className="glass-card p-8 border-slate-200 shadow-xl space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-spandan-600 to-spandan-400 flex items-center justify-center text-white mx-auto shadow-md shadow-spandan-500/20">
              <Activity className="w-7 h-7 animate-pulse" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Welcome back to Spandan</h1>
            <p className="text-sm text-slate-500">
              {initialRoleHint === 'doctor'
                ? 'Doctor Chamber Portal Login'
                : 'Sign in to your patient or chamber account'}
            </p>
          </div>

          {error && <Alert type="error" title="Login Failed" message={error} onClose={() => setError(null)} />}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field pl-10"
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Password
                </label>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pl-10"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 mt-2 font-semibold shadow-md"
            >
              {loading ? 'Signing in...' : 'Sign In'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="pt-4 border-t border-slate-100 text-center text-sm text-slate-600 space-y-2">
            <p>
              Don't have an account yet?{' '}
              <Link to="/register" className="font-semibold text-spandan-600 hover:text-spandan-700 underline">
                Register here
              </Link>
            </p>
          </div>
        </div>
      </div>
    </MainLayout>
  );
};
