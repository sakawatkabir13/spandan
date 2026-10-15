import { useLanguage } from '../../context/LanguageContext';
import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, maxWidth = 'md' }) => {
  const { t: uiText } = useLanguage();
  const titleId = useId();
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!isOpen) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close.current();
      if (event.key !== 'Tab' || !dialog.current) return;
      const controls = Array.from(dialog.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]'));
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', keydown);
    return () => {
      document.removeEventListener('keydown', keydown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [isOpen]);
  if (!isOpen) return null;
  const width = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg', xl: 'max-w-xl', '2xl': 'max-w-2xl' }[maxWidth];
  return createPortal(<div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
    <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className={`bg-white rounded-2xl shadow-2xl border border-slate-100 w-full ${width} overflow-hidden flex flex-col max-h-[calc(100dvh-2rem)]`}>
      <div className="px-4 sm:px-6 py-4 shrink-0 gap-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <h3 id={titleId} className="min-w-0 font-semibold text-lg text-slate-800">{title}</h3>
        <button type="button" aria-label={uiText("Close dialog")} onClick={onClose} className="p-2 shrink-0 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"><X className="w-5 h-5" /></button>
      </div>
      <div className="p-4 sm:p-6 overflow-y-auto overscroll-contain min-h-0 flex-1">{children}</div>
    </div>
  </div>, document.body);
};
