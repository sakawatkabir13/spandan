import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { readEvents, safeChatLink, streamMessage } from '../src/api/chat';
import { apiClient } from '../src/api/client';
import { ChatAssistant } from '../src/components/chat/ChatAssistant';

vi.mock('../src/context/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, user: { id: 'patient', role: 'patient' } }) }));
vi.mock('../src/api/client', () => ({ apiClient: { get: vi.fn(async (url: string) => ({ data: { data: url === '/service-capabilities' ? { chat: true } : [] } })), post: vi.fn() } }));
afterEach(cleanup);

describe('support chat transport and trust boundaries', () => {
  it('accepts only local screens and hosted Stripe Checkout links', () => {
    expect(safeChatLink('/dashboard/patient')).toBe('/dashboard/patient');
    expect(safeChatLink('https://checkout.stripe.com/c/pay/test')).toContain('checkout.stripe.com');
    for (const link of ['//attacker.test', '/\\attacker.test', '/\t/attacker.test', 'javascript:alert(1)', 'https://checkout.stripe.com.attacker.test/', 'https://me@checkout.stripe.com/']) expect(safeChatLink(link)).toBeUndefined();
  });
  it('preserves UTF-8 text and events split across arbitrary network chunks', async () => {
    const bytes = new TextEncoder().encode('event: text\ndata: {"text":"A doctor’s session"}\n\nevent: done\ndata: {}\n\n');
    const events: unknown[] = [];
    await readEvents(new ReadableStream({ start(controller) { for (let i = 0; i < bytes.length; i += 3) controller.enqueue(bytes.slice(i, i + 3)); controller.close(); } }), (kind, data) => events.push([kind, data]));
    expect(events).toEqual([['text', { text: 'A doctor’s session' }], ['done', {}]]);
  });
  it('reports a truncated stream instead of pretending it completed', async () => {
    const stream = new ReadableStream<Uint8Array>({ start(controller) { controller.enqueue(new TextEncoder().encode('event: text\ndata: {')); controller.close(); } });
    await expect(readEvents(stream, () => {})).rejects.toThrow('interrupted');
  });
  it('handles CRLF separators even when every byte arrives separately', async () => {
    const bytes = new TextEncoder().encode('event: text\r\ndata: {"text":"A reply"}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n');
    const events: unknown[] = [];
    await readEvents(new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close(); } }), (kind, data) => events.push([kind, data]));
    expect(events).toEqual([['text', { text: 'A reply' }], ['done', {}]]);
  });
  it('treats an unacknowledged clean EOF as an interrupted generation', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('event: text\ndata: {"text":"Incomplete"}\n\n')); controller.close(); } }) });
    await expect(streamMessage('conversation', 'Question', 'request', new AbortController().signal, () => {})).rejects.toThrow('ended early');
  });
  it('requires processing consent before a new conversation and opens accessible controls', async () => {
    render(<MemoryRouter><ChatAssistant /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Spandan Assistant' }));
    expect(screen.getByRole('dialog', { name: 'Spandan Assistant' })).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: 'Message Spandan Assistant in English' }), { target: { value: 'Find a doctor' } });
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByRole('button', { name: 'Send message' })).toBeEnabled();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
