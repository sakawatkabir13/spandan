import React from 'react';
import { Navbar } from '../common/Navbar';
import { Footer } from '../common/Footer';

export const MainLayout: React.FC<{ children: React.ReactNode; compact?: boolean }> = ({ children, compact = false }) => {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar />
      <a className="skip-link" href="#main-content">Skip to content</a>
      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {children}
      </main>
      <Footer compact={compact} />
    </div>
  );
};
