import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ size = 'md', text }) => {
  const sizeClasses = {
    sm: 'w-5 h-5 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  }[size];

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <div
        className={`${sizeClasses} border-spandan-200 border-t-spandan-600 rounded-full animate-spin`}
      />
      {text && <p className="mt-3 text-sm font-medium text-slate-600 animate-pulse">{text}</p>}
    </div>
  );
};
