import { I18nText } from '../../context/LanguageContext';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { DashboardLayout } from '../../components/layout/DashboardLayout';
import { PaymentsPanel } from '../../components/common/PaymentsPanel';

export function PaymentsPage() {
  return <DashboardLayout><div className="space-y-5"><Link to="/dashboard/patient" className="inline-flex min-h-11 items-center gap-2 text-sm text-slate-600 hover:text-spandan-700"><ArrowLeft className="h-4 w-4" /> <I18nText text={"Back to appointments"} /> </Link><h1 className="text-2xl sm:text-3xl font-bold"> <I18nText text={"Payments & receipts"} /> </h1><PaymentsPanel /></div></DashboardLayout>;
}
