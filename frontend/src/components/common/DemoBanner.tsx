import { useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import { useLanguage } from '../../context/LanguageContext';

export function DemoBanner() {
  const [demo, setDemo] = useState(false);
  const { t } = useLanguage();
  useEffect(() => {
    const controller = new AbortController();
    apiClient.get('/service-capabilities', { signal: controller.signal }).then(r => setDemo(r.data.data.demo_mode === true)).catch(() => {});
    return () => controller.abort();
  }, []);
  return demo ? <aside aria-label="Academic demo notice" className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-center text-sm text-amber-900">{t('Academic demo: appointment slots, queues and fees are simulated. No real medical consultation or payment is arranged.')}</aside> : null;
}
