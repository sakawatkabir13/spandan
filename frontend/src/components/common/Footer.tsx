import React from 'react';
import { Activity, Heart, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-slate-900 text-slate-300 pt-12 pb-8 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 pb-8 border-b border-slate-800">
          <div className="md:col-span-2 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-spandan-600 flex items-center justify-center text-white">
                <Activity className="w-5 h-5" />
              </div>
              <span className="font-bold text-xl text-white">Spandan</span>
            </div>
            <p className="text-sm text-slate-400 max-w-md leading-relaxed">
              Empowering healthcare access across Bangladesh. Seamless online serial numbers, real-time queue tracking, verified doctor profiles, and intelligent AI symptom triage for private medical chambers.
            </p>
            <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-950/40 border border-amber-800/60 p-2.5 rounded-xl max-w-md">
              <ShieldAlert className="w-4 h-4 flex-shrink-0" />
              <span>
                <strong>Safety Disclaimer:</strong> AI symptom triage is for general guidance only. In medical emergencies, immediately call 999 or visit the nearest emergency room.
              </span>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-white text-sm uppercase tracking-wider mb-3">
              Quick Navigation
            </h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link to="/doctors" className="hover:text-spandan-400 transition">
                  Find a Doctor
                </Link>
              </li>
              <li>
                <Link to="/ai-triage" className="hover:text-spandan-400 transition">
                  AI Symptom Checker
                </Link>
              </li>
              <li>
                <Link to="/login" className="hover:text-spandan-400 transition">
                  Patient Portal
                </Link>
              </li>
              <li>
                <Link to="/login?role=doctor" className="hover:text-spandan-400 transition">
                  Doctor Chamber Login
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white text-sm uppercase tracking-wider mb-3">
              About Spandan
            </h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Designed specifically for Bangladesh's private chamber practice ecosystem. Bridging the gap between early serial waiting queues and efficient doctor consultations.
            </p>
            <p className="text-xs text-slate-500 mt-4">
              © {new Date().getFullYear()} Spandan Healthcare Systems. All rights reserved.
            </p>
          </div>
        </div>

        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500">
          <p className="flex items-center gap-1">
            Built with <Heart className="w-3.5 h-3.5 text-red-500 fill-red-500" /> for accessible healthcare in Bangladesh.
          </p>
          <div className="flex gap-4 mt-2 sm:mt-0">
            <span>Privacy Policy</span>
            <span>Terms of Service</span>
            <span>BMDC Verification Guidelines</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
