import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { ApiResponse, Specialization } from '../types';
import { MainLayout } from '../components/layout/MainLayout';
import {
  ArrowRight,
  Clock,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from 'lucide-react';

export const Home: React.FC = () => {
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSpec, setSelectedSpec] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchSpecs = async () => {
      try {
        const resp = await apiClient.get<ApiResponse<Specialization[]>>('/doctors/specializations');
        if (resp.data.success) {
          setSpecializations(resp.data.data);
        }
      } catch (err) {
        // use defaults if API not running yet during initial render
      }
    };
    fetchSpecs();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (searchQuery) params.append('query', searchQuery);
    if (selectedSpec) params.append('specialization_id', selectedSpec);
    navigate(`/doctors?${params.toString()}`);
  };

  return (
    <MainLayout>
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slateDark-900 to-spandan-950 text-white p-8 sm:p-12 md:p-16 mb-16 shadow-2xl border border-slate-800">
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-96 h-96 bg-spandan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 -mb-20 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-spandan-500/20 border border-spandan-400/30 text-spandan-300 text-xs font-semibold uppercase tracking-wider mb-6">
            <Sparkles className="w-4 h-4 text-spandan-400" />
            <span>AI-Assisted Private Chamber Booking</span>
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight leading-tight mb-6">
            End the Chamber Waiting Room <span className="bg-gradient-to-r from-spandan-400 to-emerald-300 bg-clip-text text-transparent">Uncertainty.</span>
          </h1>

          <p className="text-lg text-slate-300 mb-8 max-w-2xl leading-relaxed">
            Get exact online serial numbers for private doctor consultations across Bangladesh. Track current running serials from home and use Spandan's AI medical triage to find the right specialist right when you need them.
          </p>

          {/* Quick Search Bar */}
          <form
            onSubmit={handleSearch}
            className="bg-white/95 backdrop-blur-md rounded-2xl p-3 shadow-glass flex flex-col sm:flex-row gap-3 border border-white/20 text-slate-800 max-w-2xl"
          >
            <div className="flex-1 flex items-center gap-2 px-3 border-b sm:border-b-0 sm:border-r border-slate-200 py-2 sm:py-0">
              <Search className="w-5 h-5 text-slate-400 flex-shrink-0" />
              <input
                type="text"
                placeholder="Doctor name, hospital, or symptom..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-transparent focus:outline-none text-sm placeholder-slate-400 font-medium"
              />
            </div>

            <div className="flex items-center gap-2 px-3 py-2 sm:py-0">
              <Stethoscope className="w-5 h-5 text-spandan-600 flex-shrink-0" />
              <select
                value={selectedSpec}
                onChange={(e) => setSelectedSpec(e.target.value)}
                className="bg-transparent focus:outline-none text-sm font-medium text-slate-700 cursor-pointer w-full sm:w-auto"
              >
                <option value="">All Specializations</option>
                {specializations.map((spec) => (
                  <option key={spec.id} value={spec.id}>
                    {spec.name}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              className="btn-primary py-3 sm:py-2.5 px-6 shadow-none text-sm font-semibold rounded-xl"
            >
              Search
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>
      </section>

      {/* Value Propositions */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
        <div className="glass-card p-6 border-slate-200/80 hover:border-spandan-300 transition">
          <div className="w-12 h-12 rounded-2xl bg-spandan-100 text-spandan-700 flex items-center justify-center mb-5 shadow-sm">
            <Clock className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-lg text-slate-900 mb-2">Live Serial Tracking</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Never sit in a crowded chamber for 4 hours again. Our live queue tracker displays exactly which serial number is inside the doctor's room right now and alerts you of delays.
          </p>
        </div>

        <div className="glass-card p-6 border-slate-200/80 hover:border-spandan-300 transition">
          <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-700 flex items-center justify-center mb-5 shadow-sm">
            <Sparkles className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-lg text-slate-900 mb-2">AI Symptom Triage</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Not sure whether to see a Neurologist or an ENT specialist? Enter your symptoms into our Groq Llama-powered screening engine to get precise recommendations and ER alerts.
          </p>
        </div>

        <div className="glass-card p-6 border-slate-200/80 hover:border-spandan-300 transition">
          <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center mb-5 shadow-sm">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-lg text-slate-900 mb-2">BMDC Verified Doctors</h3>
          <p className="text-sm text-slate-600 leading-relaxed">
            Every participating physician undergoes rigorous verification against their Bangladesh Medical & Dental Council (BMDC) registration number and hospital credentials.
          </p>
        </div>
      </section>

      {/* Live Demo Widget Showcase */}
      <section className="bg-gradient-to-r from-spandan-900 to-slate-900 rounded-3xl p-8 sm:p-12 text-white shadow-xl mb-16 flex flex-col md:flex-row items-center justify-between gap-8 border border-spandan-800/40">
        <div className="max-w-md space-y-4">
          <span className="text-xs font-semibold uppercase tracking-widest text-spandan-400 bg-spandan-950/60 px-3 py-1 rounded-full border border-spandan-800">
            Real-time Queue Console
          </span>
          <h2 className="text-3xl sm:text-4xl font-bold leading-tight">
            Know Exactly When It's Your Turn.
          </h2>
          <p className="text-slate-300 text-sm leading-relaxed">
            Doctors and assistants update serial status with one tap. Patients instantly see updated waiting times and delay notifications.
          </p>
          <div className="pt-2">
            <Link
              to="/doctors"
              className="btn-primary inline-flex py-3 px-6 text-sm font-semibold shadow-lg shadow-spandan-500/30"
            >
              Book Your First Serial Now
            </Link>
          </div>
        </div>

        {/* Mockup Card */}
        <div className="w-full md:w-96 bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6 shadow-2xl space-y-4 text-slate-100">
          <div className="flex items-center justify-between pb-3 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-spandan-500 flex items-center justify-center font-bold text-white shadow">
                DR
              </div>
              <div>
                <h4 className="font-bold text-sm">Dr. Cardio Specialist</h4>
                <p className="text-xs text-spandan-300">Cardio Care Dhanmondi</p>
              </div>
            </div>
            <span className="bg-emerald-500/20 text-emerald-300 text-[10px] font-bold px-2.5 py-1 rounded-full border border-emerald-400/30 animate-pulse">
              LIVE QUEUE
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="bg-white/5 rounded-xl p-3 border border-white/10 text-center">
              <span className="text-[11px] text-slate-400 uppercase block font-medium">Running Serial</span>
              <span className="text-3xl font-extrabold text-spandan-400">#14</span>
            </div>
            <div className="bg-white/5 rounded-xl p-3 border border-white/10 text-center">
              <span className="text-[11px] text-slate-400 uppercase block font-medium">Your Serial</span>
              <span className="text-3xl font-extrabold text-white">#18</span>
            </div>
          </div>

          <div className="bg-spandan-500/10 rounded-xl p-3 border border-spandan-400/20 text-xs space-y-1">
            <div className="flex justify-between font-medium">
              <span className="text-slate-300">People ahead:</span>
              <span className="text-white font-bold">4 patients</span>
            </div>
            <div className="flex justify-between font-medium">
              <span className="text-slate-300">Est. waiting time:</span>
              <span className="text-spandan-300 font-bold">~60 mins</span>
            </div>
          </div>

          <div className="text-center text-[11px] text-slate-400 italic">
            "Doctor is inside chamber and examining serial #14."
          </div>
        </div>
      </section>

      {/* Specializations Grid */}
      <section className="mb-16">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">Explore Medical Specialties</h2>
            <p className="text-sm text-slate-600">Find experienced chamber specialists across common departments.</p>
          </div>
          <Link to="/doctors" className="text-sm font-semibold text-spandan-600 hover:text-spandan-700 flex items-center gap-1">
            View All <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {specializations.slice(0, 10).map((spec) => (
            <Link
              key={spec.id}
              to={`/doctors?specialization_id=${spec.id}`}
              className="glass-card p-4 text-center border-slate-200/70 hover:border-spandan-400 transition group flex flex-col items-center justify-center"
            >
              <div className="w-10 h-10 rounded-xl bg-spandan-50 text-spandan-600 flex items-center justify-center mb-3 group-hover:scale-110 group-hover:bg-spandan-600 group-hover:text-white transition duration-200 shadow-sm">
                <Stethoscope className="w-5 h-5" />
              </div>
              <h4 className="font-semibold text-sm text-slate-800 group-hover:text-spandan-700 transition">
                {spec.name}
              </h4>
            </Link>
          ))}
        </div>
      </section>
    </MainLayout>
  );
};
