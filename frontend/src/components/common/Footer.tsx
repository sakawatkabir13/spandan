import { I18nText } from '../../context/LanguageContext';
import { useLanguage } from '../../context/LanguageContext';
import React from 'react';
import { Activity, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Footer: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { t: uiText } = useLanguage();
  if (compact) return <footer className="border-t border-slate-200 bg-white py-5 text-xs text-slate-500"><div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-3"><p>© {new Date().getFullYear()}  <I18nText text={"Spandan"} /> </p><nav aria-label={uiText("Legal information")} className="flex flex-wrap gap-x-4 gap-y-2"><Link to="/privacy" className="hover:text-spandan-700"> <I18nText text={"Privacy policy"} /> </Link><Link to="/terms" className="hover:text-spandan-700"> <I18nText text={"Terms of service"} /> </Link><Link to="/medical-disclaimer" className="hover:text-spandan-700"> <I18nText text={"Medical disclaimer"} /> </Link></nav></div></footer>;
  return (
    <footer className="bg-slate-900 text-slate-300 pt-12 pb-8 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 pb-8 border-b border-white/10">
          <div className="md:col-span-2 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-spandan-600 flex items-center justify-center text-white">
                <Activity className="w-5 h-5" />
              </div>
              <span className="font-bold text-xl text-white"> <I18nText text={"Spandan"} /> </span>
            </div>
            <p className="text-sm text-slate-400 max-w-md leading-relaxed">
               <I18nText text={"Find a doctor, prepare for your appointment, and follow your queue in one place. Care, closer to you."} /> </p>
            <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-950/40 border border-amber-800/60 p-2.5 rounded-xl max-w-md">
              <ShieldAlert className="w-4 h-4 flex-shrink-0" />
              <span>
                <strong> <I18nText text={"Safety Disclaimer:"} /> </strong>  <I18nText text={"AI symptom triage is for general guidance only. In medical emergencies, immediately call 999 or visit the nearest emergency room."} /> </span>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-white text-sm uppercase tracking-wider mb-3">
               <I18nText text={"Quick Navigation"} /> </h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link to="/doctors" className="hover:text-spandan-400 transition">
                   <I18nText text={"Find a Doctor"} /> </Link>
              </li>
              <li>
                <Link to="/ai-triage" className="hover:text-spandan-400 transition">
                   <I18nText text={"AI Symptom Checker"} /> </Link>
              </li>
              <li>
                <Link to="/login" className="hover:text-spandan-400 transition">
                   <I18nText text={"Patient Portal"} /> </Link>
              </li>
              <li>
                <Link to="/login?role=doctor" className="hover:text-spandan-400 transition">
                   <I18nText text={"Doctor Chamber Login"} /> </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white text-sm uppercase tracking-wider mb-3">
               <I18nText text={"About Spandan"} /> </h4>
            <p className="text-xs text-slate-400 leading-relaxed">
               <I18nText text={"Appointments and private chamber management for patients, doctors, and care teams across Bangladesh."} /> </p>
            <p className="text-xs text-slate-500 mt-4">
              © {new Date().getFullYear()}  <I18nText text={"Spandan Healthcare Systems. All rights reserved."} /> </p>
          </div>
        </div>

        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500">
          <p className="flex items-center gap-1">
             <I18nText text="Care, closer to you." /> </p>
          <div className="flex gap-4 mt-2 sm:mt-0">
            <Link to="/privacy" className="hover:text-spandan-400 transition"> <I18nText text={"Privacy Policy"} /> </Link>
            <Link to="/terms" className="hover:text-spandan-400 transition"> <I18nText text={"Terms of Service"} /> </Link>
            <Link to="/medical-disclaimer" className="hover:text-spandan-400 transition"> <I18nText text={"Medical Disclaimer"} /> </Link>
          </div>
        </div>
      </div>
    </footer>
  );
};
