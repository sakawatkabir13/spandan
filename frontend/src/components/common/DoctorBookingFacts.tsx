import { I18nText, useLanguage } from '../../context/LanguageContext';
import { Clock3, Heart } from 'lucide-react';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { useAuth } from '../../context/AuthContext';

export type DoctorFacts = { languages: string; minimum_patient_age: number | null; maximum_patient_age: number | null; chambers: { id: string; name: string; area: string; district: string; consultation_fee: number; follow_up_fee: number | null }[]; next_session: { id: string; date: string; start_time: string; confirmed_at: string | null; chamber_id: string } | null };
export function DoctorBookingFacts({ facts, sourced }: { facts?: DoctorFacts; sourced?: boolean }) {
  const { t } = useLanguage();
  if (!facts) return null;
  const fees = facts.chambers.map(c => Number(c.consultation_fee));
  const followUp = facts.chambers.filter(c => c.follow_up_fee !== null).map(c => Number(c.follow_up_fee));
  const nextChamber = facts.chambers.find(chamber => chamber.id === facts.next_session?.chamber_id);
  return <div className="mt-4 space-y-2 border-t border-slate-100 pt-3 text-xs text-slate-600"><div className="flex flex-wrap gap-x-4 gap-y-2">{fees.length > 0 && <p> <I18nText text={"Consultation"} /> <strong className="text-slate-800"> <I18nText text={"from ৳"} /> {Math.min(...fees).toLocaleString('en-BD')}</strong></p>}{followUp.length > 0 && <p> <I18nText text={"Follow-up from ৳"} /> {Math.min(...followUp).toLocaleString('en-BD')}</p>}</div>{facts.chambers.length > 0 && <p>{[...new Set(facts.chambers.map(chamber => [chamber.area, chamber.district].filter(Boolean).join(', ')))].join(' · ')}</p>}<p className="flex items-start gap-1.5"><Clock3 className="h-3.5 w-3.5 shrink-0" />{facts.next_session ? `${t('Next session:')} ${new Date(`${facts.next_session.date}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}, ${facts.next_session.start_time.slice(0, 5)} · ${nextChamber?.name || ''} · ${t(sourced || !facts.next_session.confirmed_at ? 'Confirm availability with chamber' : 'Published by chamber staff')}` : t('No open session currently listed')}</p>{facts.languages && <p> <I18nText text={"Languages:"} /> {facts.languages}</p>}{(facts.minimum_patient_age !== null || facts.maximum_patient_age !== null) && <p> <I18nText text={"Patient ages:"} /> {facts.minimum_patient_age ?? 0}–{facts.maximum_patient_age ?? 'all ages'}</p>}</div>;
}

export function SaveDoctorButton({ doctorId }: { doctorId: string }) {
  const { user } = useAuth();
  return user?.role === 'patient' ? <PatientSaveDoctorButton doctorId={doctorId} /> : null;
}

function PatientSaveDoctorButton({ doctorId }: { doctorId: string }) {
  const { user } = useAuth();
  const { t } = useLanguage();
  const cache = useQueryClient();
  const { data: savedIds = [], isPending } = useQuery<string[]>({ queryKey: ['favorite-doctors', user?.id], queryFn: async () => (await apiClient.get('/patients/me/favorites')).data.data, enabled: user?.role === 'patient' });
  const saved = savedIds.includes(doctorId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (user?.role !== 'patient') return null;
  return <div><button type="button" aria-pressed={saved} aria-label={t(saved ? 'Remove saved doctor' : 'Save doctor')} className="btn-secondary text-sm" disabled={busy || isPending} onClick={async () => { setBusy(true); setError(''); try { await apiClient.put(`/patients/me/favorites/${doctorId}?saved=${!saved}`); cache.setQueryData(['favorite-doctors', user?.id], saved ? savedIds.filter(id => id !== doctorId) : [...savedIds, doctorId]); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}><Heart className={`h-4 w-4 ${saved ? 'fill-spandan-600 text-spandan-600' : ''}`} />{t(saved ? 'Saved' : 'Save doctor')}</button>{error && <p role="alert" className="mt-2 max-w-xs text-xs text-red-700">{error}</p>}</div>;
}
