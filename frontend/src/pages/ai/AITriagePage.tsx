import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ApiResponse, SpecialistRecommendation } from '../../types';
import { MainLayout } from '../../components/layout/MainLayout';
import { Alert } from '../../components/common/Alert';
import { Badge } from '../../components/common/Badge';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import {
  AlertTriangle,
  ArrowRight,
  History,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';

export const AITriagePage: React.FC = () => {
  const { user, isAuthenticated } = useAuth();

  const [symptomsText, setSymptomsText] = useState('');
  const [age, setAge] = useState<string>('');
  const [gender, setGender] = useState<string>('Not Specified');
  const [durationDays, setDurationDays] = useState<string>('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SpecialistRecommendation | null>(null);

  const [history, setHistory] = useState<SpecialistRecommendation[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const fetchHistory = async () => {
    if (!isAuthenticated || user?.role !== 'patient') return;
    setHistoryLoading(true);
    try {
      const resp = await apiClient.get<ApiResponse<SpecialistRecommendation[]>>('/ai/recommendations/me');
      if (resp.data.success) {
        setHistory(resp.data.data);
      }
    } catch (err) {
      // ignore
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [isAuthenticated]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);

    try {
      const resp = await apiClient.post<ApiResponse<SpecialistRecommendation>>('/ai/symptom-check', {
        symptoms_text: symptomsText,
        age: age ? Number(age) : undefined,
        gender: gender !== 'Not Specified' ? gender : undefined,
        duration_days: durationDays ? Number(durationDays) : undefined,
      });

      if (resp.data.success) {
        setResult(resp.data.data);
        fetchHistory();
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || 'Failed to analyze symptoms. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Banner */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-slate-900 via-spandan-950 to-slate-900 text-white p-8 shadow-xl border border-slate-800">
          <div className="absolute top-0 right-0 -mr-16 -mt-16 w-80 h-80 bg-spandan-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-2 max-w-xl">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-spandan-500/20 text-spandan-300 text-xs font-semibold uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5" /> Groq Llama Powered Triage
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">AI Medical Symptom Checker</h1>
              <p className="text-sm text-slate-300 leading-relaxed">
                Describe your health symptoms in your own words. Our medical triage engine will screen for emergency red flags and recommend the exact specialist department for your chamber appointment.
              </p>
            </div>
          </div>
        </div>

        {/* Input Form */}
        <div className="glass-card p-6 sm:p-8 border-slate-200 shadow-lg space-y-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-slate-800 mb-1.5">
                Describe your symptoms in detail <span className="text-red-500">*</span>
              </label>
              <textarea
                required
                rows={4}
                minLength={10}
                maxLength={1200}
                placeholder="e.g., I have been experiencing severe headaches radiating to my neck along with dizziness for the last 4 days. Mild nausea is also present..."
                value={symptomsText}
                onChange={(e) => setSymptomsText(e.target.value)}
                className="input-field bg-white"
              />
              <p className="text-xs text-slate-500 mt-1">
                Please provide specific details such as pain location, intensity, and any triggers.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Patient Age
                </label>
                <input
                  type="number"
                  min={0}
                  max={120}
                  placeholder="e.g., 34"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  className="input-field bg-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Gender
                </label>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="input-field bg-white cursor-pointer"
                >
                  <option value="Not Specified">Not Specified</option>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
                  Duration (in Days)
                </label>
                <input
                  type="number"
                  min={0}
                  max={365}
                  placeholder="e.g., 3"
                  value={durationDays}
                  onChange={(e) => setDurationDays(e.target.value)}
                  className="input-field bg-white"
                />
              </div>
            </div>

            {error && <Alert type="error" message={error} />}

            <button
              type="submit"
              disabled={loading || !symptomsText.trim()}
              className="btn-primary py-3.5 px-8 font-semibold w-full sm:w-auto shadow-md"
            >
              {loading ? 'Analyzing with AI Triage Engine...' : 'Analyze Symptoms & Find Specialist'}
              <Sparkles className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Triage Results Display */}
        {loading && <LoadingSpinner size="lg" text="AI screening symptoms for emergency red flags and department mapping..." />}

        {result && (
          <div
            className={`glass-card p-6 sm:p-8 shadow-2xl border-2 transition animate-fade-in ${
              result.urgency_level === 'emergency'
                ? 'bg-red-50/90 border-red-500 text-red-950'
                : 'bg-white border-spandan-500/60'
            }`}
          >
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-200/60">
              <div className="space-y-1">
                <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
                  Triage Recommendation Result
                </span>
                <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                  {result.recommended_specialization_name}
                </h2>
                {result.alternative_specialization_name && (
                  <p className="text-xs text-slate-600">
                    Alternative specialty: <strong>{result.alternative_specialization_name}</strong>
                  </p>
                )}
              </div>

              <Badge
                variant={
                  result.urgency_level === 'emergency'
                    ? 'danger'
                    : result.urgency_level === 'urgent'
                    ? 'warning'
                    : 'success'
                }
                className="px-3 py-1 text-xs uppercase font-bold"
              >
                {result.urgency_level === 'emergency' ? '🚨 CRITICAL ER ALERT' : `Urgency: ${result.urgency_level}`}
              </Badge>
            </div>

            {/* Emergency Alert Card */}
            {result.urgency_level === 'emergency' && (
              <div className="mt-4 bg-red-600 text-white p-5 rounded-2xl shadow-lg space-y-3">
                <div className="flex items-center gap-2 font-bold text-lg">
                  <AlertTriangle className="w-6 h-6 animate-pulse" />
                  EMERGENCY ACTION REQUIRED IMMEDIATELY
                </div>
                <p className="text-sm font-medium leading-relaxed">{result.safety_message}</p>
                <div className="pt-2">
                  <a
                    href="tel:999"
                    className="inline-flex items-center gap-2 bg-white text-red-700 font-extrabold px-6 py-3 rounded-xl shadow hover:bg-red-50 transition text-base"
                  >
                    Call Ambulance (999) Now
                  </a>
                </div>
              </div>
            )}

            {/* Medical Reasoning & Safety */}
            <div className="mt-6 space-y-4 text-slate-800">
              <div>
                <h4 className="font-semibold text-sm text-slate-900 mb-1">Medical Rationale:</h4>
                <p className="text-sm leading-relaxed text-slate-700 bg-slate-50/80 p-4 rounded-xl border border-slate-200/60">
                  {result.reasoning_summary}
                </p>
              </div>

              {result.urgency_level !== 'emergency' && result.safety_message && (
                <div>
                  <h4 className="font-semibold text-sm text-slate-900 mb-1">Symptom Monitoring & Self-Care:</h4>
                  <p className="text-sm leading-relaxed text-slate-700 bg-amber-50/60 p-4 rounded-xl border border-amber-200/60">
                    {result.safety_message}
                  </p>
                </div>
              )}

              <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
                <div className="text-[11px] text-slate-500 italic flex items-center gap-1.5 max-w-lg">
                  <ShieldAlert className="w-4 h-4 flex-shrink-0 text-amber-500" />
                  {result.disclaimer}
                </div>

                {result.urgency_level !== 'emergency' && (
                  <Link
                    to={`/doctors?query=${encodeURIComponent(result.recommended_specialization_name)}`}
                    className="btn-primary py-3 px-6 text-sm font-semibold whitespace-nowrap shadow-lg"
                  >
                    Book {result.recommended_specialization_name} Doctor
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}

        {/* History of Past Triage Checks */}
        {isAuthenticated && user?.role === 'patient' && (
          historyLoading ? (
            <div className="glass-card p-6 border-slate-200 flex justify-center">
              <LoadingSpinner size="sm" text="Loading previous triage checks..." />
            </div>
          ) : history.length > 0 ? (
          <div className="glass-card p-6 border-slate-200 space-y-4">
            <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
              <History className="w-5 h-5 text-spandan-600" /> Your Previous Symptom Checks
            </h3>
            <div className="space-y-3">
              {history.slice(0, 5).map((item) => (
                <div
                  key={item.id}
                  className="p-4 rounded-xl border border-slate-200/80 bg-white/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">{item.recommended_specialization_name}</span>
                      <Badge variant={item.urgency_level === 'emergency' ? 'danger' : 'neutral'}>
                        {item.urgency_level}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-600 line-clamp-1 italic">"{item.symptoms_text}"</p>
                  </div>
                  <span className="text-xs text-slate-400 font-medium whitespace-nowrap">
                    {new Date(item.created_at).toLocaleDateString('en-GB')}
                  </span>
                </div>
              ))}
            </div>
          </div>
          ) : null
        )}
      </div>
    </MainLayout>
  );
};
