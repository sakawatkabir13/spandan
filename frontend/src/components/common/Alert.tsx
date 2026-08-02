import React from 'react';
import { AlertCircle, CheckCircle, Info, XCircle } from 'lucide-react';

interface AlertProps {
  type?: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  message: string;
  onClose?: () => void;
}

export const Alert: React.FC<AlertProps> = ({ type = 'info', title, message, onClose }) => {
  const styles = {
    success: {
      bg: 'bg-green-50 border-green-200 text-green-900',
      icon: <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />,
    },
    error: {
      bg: 'bg-red-50 border-red-200 text-red-900',
      icon: <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />,
    },
    warning: {
      bg: 'bg-amber-50 border-amber-200 text-amber-900',
      icon: <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />,
    },
    info: {
      bg: 'bg-blue-50 border-blue-200 text-blue-900',
      icon: <Info className="w-5 h-5 text-blue-600 flex-shrink-0" />,
    },
  }[type];

  return (
    <div className={`p-4 rounded-xl border flex items-start gap-3 shadow-sm ${styles.bg}`}>
      {styles.icon}
      <div className="flex-1">
        {title && <h4 className="font-semibold text-sm mb-0.5">{title}</h4>}
        <p className="text-sm leading-relaxed">{message}</p>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 transition p-1 rounded-lg"
        >
          ×
        </button>
      )}
    </div>
  );
};
