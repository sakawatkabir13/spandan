import { useEffect, useRef, useState } from 'react';
import { apiClient } from '../api/client';

export function useLiveQueue(scheduleId: string | undefined, refresh: () => void | Promise<void>) {
  const latest = useRef(refresh);
  latest.current = refresh;
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  useEffect(() => {
    if (!scheduleId) return;
    const controller = new AbortController();
    let retry: ReturnType<typeof setTimeout>;
    const connect = async () => {
      try {
        const response = await fetch(`${apiClient.defaults.baseURL || '/api/v1'}/events/queue/${scheduleId}`, { signal: controller.signal });
        if (!response.ok || !response.body) throw new Error('Live queue unavailable');
        setConnected(true);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split('\n\n');
          buffer = messages.pop() || '';
          for (const message of messages) {
            setLastUpdate(new Date());
            if (message.includes('event: queue')) void latest.current();
          }
        }
      } catch {
        if (controller.signal.aborted) return;
      }
      setConnected(false);
      if (!controller.signal.aborted) retry = setTimeout(connect, 5000);
    };
    void connect();
    const offline = () => setConnected(false);
    window.addEventListener('offline', offline);
    return () => { controller.abort(); clearTimeout(retry); window.removeEventListener('offline', offline); };
  }, [scheduleId]);
  return { connected, lastUpdate };
}
