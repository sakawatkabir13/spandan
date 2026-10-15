import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ChatDetails, ChatResultCard, ChatText } from '../src/components/chat/ChatContent';
import { ChatActionCard } from '../src/components/chat/ChatActionCard';
import { apiClient } from '../src/api/client';

vi.mock('../src/api/client', () => ({ apiClient: { get: vi.fn(), post: vi.fn() } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('readable support answers and explicit actions', () => {
  it('renders helpful Markdown without remote images, HTML, or unsafe links', () => {
    const navigate = vi.fn();
    const { container } = render(<MemoryRouter><ChatText onNavigate={navigate} text={'## Your next steps\n\n1. **Choose a doctor**\n2. [See appointments](/dashboard/patient)\n\n| Fee | Amount |\n| --- | --- |\n| Visit | BDT 500 |\n\n![tracker](https://tracker.example/pixel)\n\n<script>alert(1)</script>\n\n[unsafe](javascript:alert) [external](https://attacker.example)'} /></MemoryRouter>);
    expect(screen.getByRole('heading', { name: 'Your next steps' })).toBeVisible();
    expect(container.querySelector('strong')).toHaveTextContent('Choose a doctor');
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(container.querySelector('img, script')).toBeNull();
    expect(screen.queryByRole('link', { name: 'unsafe' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'external' })).toBeNull();
    fireEvent.click(screen.getByRole('link', { name: 'See appointments' }));
    expect(navigate).toHaveBeenCalledTimes(1);
  });
  it('preserves the exact proposed changes while keeping internal identifiers out of the details', () => {
    render(<ChatDetails value={{ doctor_name: 'Dr Exact Target', attendee_name: 'Child Profile', doctor_id: 'private-uuid', session_date: '2026-12-01', consultation_fee: '500.00', currency: 'bdt', requested_changes: { status: 'cancelled', can_update_queue: false, can_manage_schedules: true } }} />);
    for (const text of ['Dr Exact Target', 'Child Profile', '1 Dec 2026', 'BDT 500.00', 'Cancelled', 'No', 'Yes']) expect(screen.getByText(text)).toBeVisible();
    expect(screen.queryByText('private-uuid')).toBeNull();
  });
  it('keeps long result lists compact, then paginates with the current filters', () => {
    const ask = vi.fn();
    const items = Array.from({ length: 5 }, (_, i) => ({ id: String(i), full_name: `Dr Specialist ${i}`, specialties: ['Medicine'], availability_note: 'Contact the hospital to confirm availability.', href: `/doctors/${i}` }));
    render(<MemoryRouter><ChatResultCard card={{ tool: 'search_doctors', data: { items, next_offset: 10 } }} ask={ask} onNavigate={() => {}} /></MemoryRouter>);
    expect(screen.getAllByRole('link', { name: 'View doctor & sessions' })).toHaveLength(3);
    expect(screen.queryByText('Dr Specialist 4')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show 2 more in this reply' }));
    expect(screen.getByText('Dr Specialist 4')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Show more results' }));
    expect(ask).toHaveBeenCalledWith(expect.stringContaining('offset 10. Keep my previous filters.'));
  });
  it('never confirms expired proposals and explains why a new one is needed', () => {
    render(<MemoryRouter><ChatActionCard action={{ id: 'expired', name: 'propose_checkout', status: 'pending', requires_step_up: false, expires_at: new Date(Date.now() - 1000).toISOString(), summary: { amount: 500, currency: 'bdt' } }} update={() => {}} onNavigate={() => {}} /></MemoryRouter>);
    expect(screen.getByText(/This proposal expired/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull();
    expect(apiClient.post).not.toHaveBeenCalled();
  });
  it('keeps sensitive credentials in the secure verification form and explains cash refund consequences', () => {
    render(<MemoryRouter><ChatActionCard action={{ id: 'refund', name: 'propose_refund', status: 'pending', requires_step_up: true, expires_at: new Date(Date.now() + 300000).toISOString(), summary: { doctor_name: 'Dr Exact Target', amount: 500, currency: 'bdt' } }} update={() => {}} onNavigate={() => {}} /></MemoryRouter>);
    expect(screen.getByText(/does not physically return money/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Verify & confirm' }));
    expect(screen.getByRole('dialog', { name: 'Verify this action' })).toBeVisible();
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
