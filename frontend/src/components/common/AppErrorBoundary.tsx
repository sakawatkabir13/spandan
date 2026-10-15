import { I18nText } from '../../context/LanguageContext';
import { Component, ReactNode } from 'react';

export class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <main className="mx-auto flex min-h-[70dvh] max-w-lg flex-col justify-center px-6"><h1 className="page-heading"> <I18nText text={"This page couldn't be loaded"} /> </h1><p className="page-description"> <I18nText text={"Reload to reconnect. Your confirmed appointments and payments are saved."} /> </p><button className="btn-primary mt-6 self-start" onClick={() => window.location.reload()}> <I18nText text={"Reload page"} /> </button></main>;
    return this.props.children;
  }
}
