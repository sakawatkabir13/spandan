import { apiClient } from './client';

export type ChatAction = {
  id: string; name: string; status: string; requires_step_up: boolean; expires_at: string;
  summary: Record<string, unknown>; error_code?: string;
  result?: { message: string; href?: string; checkout_url?: string; [key: string]: unknown };
};
export type ToolCard = { tool: string; data: { proposal?: ChatAction; items?: Record<string, unknown>[]; next_offset?: number | null; [key: string]: unknown } };
export type ChatMessage = { id?: string; role: 'user' | 'assistant'; text: string; cards?: ToolCard[] };
export type Conversation = { id: string; title: string; created_at: string; expires_at: string };

export async function readEvents(stream: ReadableStream<Uint8Array>, onEvent: (event: string, data: any) => void) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n');
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const type = block.split('\n').find(line => line.startsWith('event:'))?.slice(6).trim() || 'message';
        const data = block.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (data) onEvent(type, JSON.parse(data));
      }
      if (done) break;
    }
    if (buffer.trim()) throw new Error('The support response was interrupted. Reload the conversation before retrying.');
  } finally { reader.releaseLock(); }
}

export async function streamMessage(conversationId: string, text: string, clientMessageId: string,
  signal: AbortSignal, onEvent: (event: string, data: any) => void) {
  // Axios' fetch adapter retains the application's refresh-token interceptor while exposing SSE.
  const response = await apiClient.post(`/chat/conversations/${conversationId}/messages`,
    { text, client_message_id: clientMessageId },
    { adapter: 'fetch', responseType: 'stream', timeout: 0, signal, headers: { Accept: 'text/event-stream' } });
  await readEvents(response.data, onEvent);
}

export function safeChatLink(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  if (value.startsWith('/') && !value.startsWith('//') && !value.includes('\\')) return value;
  try { const url = new URL(value); if (url.protocol === 'https:' && url.hostname === 'checkout.stripe.com' && !url.username && !url.password) return value; } catch { /* Ignore invalid links. */ }
  return undefined;
}
