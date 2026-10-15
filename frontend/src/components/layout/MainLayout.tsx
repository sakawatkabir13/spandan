import { I18nText } from '../../context/LanguageContext';
import React from 'react';
import { Navbar } from '../common/Navbar';
import { Footer } from '../common/Footer';
import { PatientNavigation } from '../common/PatientNavigation';
import { useAuth } from '../../context/AuthContext';

export const MainLayout: React.FC<{ children: React.ReactNode; compact?: boolean }> = ({ children, compact = false }) => {
  const { user } = useAuth();
  return (
    <div className={`min-h-screen flex flex-col ${user?.role === 'patient' ? 'patient-shell' : ''}`}>
      <Navbar />
      <a className="skip-link" href="#main-content"> <I18nText text={"Skip to content"} /> </a>
      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {children}
      </main>
      <Footer compact={compact} />
      <PatientNavigation />
    </div>
  );
};
