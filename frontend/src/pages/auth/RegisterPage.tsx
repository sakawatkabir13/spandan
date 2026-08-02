import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { MainLayout } from '../../components/layout/MainLayout';
import { Alert } from '../../components/common/Alert';
import { Activity, ArrowRight, Lock, Mail, Phone, Stethoscope, User as UserIcon } from 'lucide-react';

export const RegisterPage: React.FC = () => {
  const [tab, setTab] = useState<'patient' | 'doctor'>('patient');

  // Common fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [fullName, setFullName] = useState('');

  // Doctor specific fields
  const [bmdcNumber, setBmdcNumber] = useState('');
  const [workplace, setWorkplace] = useState('');
  const [experienceYears, setExperienceYears] = useState(5);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { registerPatient, registerDoctor } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (tab === 'patient') {
        await registerPatient({
          email,
          password,
          phone_number: phoneNumber,
          full_name: fullName,
        });
        navigate('/dashboard/patient');
      } else {
        await registerDoctor({
          email,
          password,
          phone_number: phoneNumber,
          full_name: fullName,
          medical_registration_number: bmdcNumber,
          current_workplace: workplace || undefined,
          years_of_experience: Number(experienceYears),
        });
        navigate('/dashboard/doctor');
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Registration failed. Please check your inputs.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="max-w-xl mx-auto py-8">
        <div className="glass-card p-8 border-slate-200 shadow-xl space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-spandan-600 to-spandan-400 flex items-center justify-center text-white mx-auto shadow-md shadow-spandan-500/20">
              <Activity className="w-7 h-7 animate-pulse" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Create your Spandan account</h1>
            <p className="text-sm text-slate-500">Choose your account type below to get started</p>
          </div>

          {/* Toggle Tabs */}
          <div className="grid grid-cols-2 gap-2 bg-slate-100 p-1.5 rounded-2xl">
            <button
              type="button"
              onClick={() => {
                setTab('patient');
                setError(null);
              }}
              className={`py-2.5 px-4 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2 ${
                tab === 'patient'
                  ? 'bg-white text-spandan-800 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <UserIcon className="w-4 h-4" />
              Patient Account
            </button>
            <button
              type="button"
              onClick={() => {
                setTab('doctor');
                setError(null);
              }}
              className={`py-2.5 px-4 rounded-xl text-sm font-semibold transition flex items-center justify-center gap-2 ${
                tab === 'doctor'
                  ? 'bg-white text-spandan-800 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Stethoscope className="w-4 h-4" />
              Doctor Practitioner
            </button>
          </div>

          {error && <Alert type="error" title="Registration Error" message={error} onClose={() => setError(null)} />}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Full Name
              </label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="text"
                  required
                  placeholder={tab === 'patient' ? 'e.g. Rahat Karim' : 'e.g. Dr. Tanvir Ahmed'}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="input-field pl-10"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                  <input
                    type="email"
                    required
                    placeholder="name@gmail.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field pl-10"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Phone Number
                </label>
                <div className="relative">
                  <Phone className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                  <input
                    type="text"
                    required
                    placeholder="01712345678 or +8801712345678"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="input-field pl-10"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="password"
                  required
                  placeholder="At least 8 characters with letters and digits"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pl-10"
                />
              </div>
            </div>

            {/* Doctor specific fields */}
            {tab === 'doctor' && (
              <div className="bg-spandan-50/50 p-4 rounded-2xl border border-spandan-200/60 space-y-4 animate-fade-in">
                <div className="flex items-center gap-2 text-spandan-800 font-semibold text-xs uppercase tracking-wider">
                  <Stethoscope className="w-4 h-4 text-spandan-600" />
                  <span>BMDC & Professional Credentials</span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    BMDC Registration Number (Required)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. A-12345 or BMDC-A-10101"
                    value={bmdcNumber}
                    onChange={(e) => setBmdcNumber(e.target.value)}
                    className="input-field bg-white"
                  />
                  <p className="text-[11px] text-slate-500 mt-1">
                    Your BMDC number will be verified by Spandan administrators.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Current Hospital / Workplace
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. BSMMU / Dhaka Medical"
                      value={workplace}
                      onChange={(e) => setWorkplace(e.target.value)}
                      className="input-field bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Years of Experience
                    </label>
                    <input
                      type="number"
                      required
                      min={0}
                      max={70}
                      value={experienceYears}
                      onChange={(e) => setExperienceYears(Number(e.target.value))}
                      className="input-field bg-white"
                    />
                  </div>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 mt-4 font-semibold shadow-md"
            >
              {loading ? 'Creating account...' : `Register as ${tab === 'patient' ? 'Patient' : 'Doctor'}`}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <div className="pt-4 border-t border-slate-100 text-center text-sm text-slate-600">
            Already registered?{' '}
            <Link to="/login" className="font-semibold text-spandan-600 hover:text-spandan-700 underline">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </MainLayout>
  );
};
