import { useState } from 'react';
import { apiClient } from '../../api/client';
import { errorMessage } from '../../api/errors';
import { Chamber, Schedule } from '../../types';

export function ChamberEditor({ chamber, saved }: { chamber: Chamber; saved: () => void }) {
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  return <form className="space-y-3" onSubmit={async e => {
    e.preventDefault(); setBusy(true);
    const fields: any = Object.fromEntries(new FormData(e.currentTarget));
    fields.consultation_fee = Number(fields.consultation_fee);
    fields.follow_up_fee = Number(fields.follow_up_fee);
    fields.is_active = fields.is_active === 'true';
    try { await apiClient.patch(`/chambers/${chamber.id}`, fields); saved(); }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(false); }
  }}>
    {message && <p role="alert">{message}</p>}
    {['name', 'address', 'district', 'area', 'phone_number', 'consultation_fee', 'follow_up_fee'].map(key =>
      <label key={key} className="block text-sm">{key.replaceAll('_', ' ')}
        <input aria-label={key.replaceAll('_', ' ')} name={key} required={key !== 'phone_number'} type={key.endsWith('fee') ? 'number' : 'text'} min={0} defaultValue={(chamber as any)[key] ?? ''} className="input-field" />
      </label>)}
    <label className="block">Availability<select name="is_active" defaultValue={String(chamber.is_active)} className="input-field"><option value="true">Active</option><option value="false">Inactive</option></select></label>
    <button className="btn-primary" disabled={busy}>Save Chamber</button>
  </form>;
}

export function ScheduleEditor({ schedule, saved }: { schedule: Schedule; saved: () => void }) {
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  return <form className="space-y-3" onSubmit={async e => {
    e.preventDefault(); setBusy(true);
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    const changes: any = {};
    for (const [key, raw] of Object.entries(fields)) {
      const value = ['maximum_patients', 'average_consultation_minutes'].includes(key) ? Number(raw) : `${raw}:00`;
      if (key !== 'series' && value !== (schedule as any)[key]) changes[key] = value;
    }
    const target = fields.series === 'on' && (schedule as any).series_id ? `/schedules/series/${(schedule as any).series_id}?from_date=${schedule.schedule_date}` : `/schedules/${schedule.id}`;
    try { if (Object.keys(changes).length) await apiClient.patch(target, changes); saved(); }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(false); }
  }}>
    <p className="text-sm text-slate-600">Times can only change before bookings exist. Capacity cannot be reduced below current bookings.</p>
    {message && <p role="alert">{message}</p>}
    {['start_time', 'end_time', 'maximum_patients', 'average_consultation_minutes'].map(key =>
      <label key={key} className="block">{key.replaceAll('_', ' ')}<input name={key} type={key.endsWith('time') ? 'time' : 'number'} min={1} required defaultValue={key.endsWith('time') ? (schedule as any)[key].slice(0, 5) : (schedule as any)[key]} className="input-field" /></label>)}
    {(schedule as any).series_id && <label className="block"><input name="series" type="checkbox" /> Apply to this and later sessions in the recurring series</label>}
    <button disabled={busy} className="btn-primary">Save Session</button>
  </form>;
}
