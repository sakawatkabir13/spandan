import { useEffect, useRef, useState } from 'react';
import { AnnotationMode, GlobalWorkerOptions, getDocument, type PDFDocumentProxy, type RenderTask } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { I18nText, useLanguage } from '../../context/LanguageContext';

GlobalWorkerOptions.workerSrc = workerUrl;

export default function PdfReportPreview({ data }: { data: Uint8Array }) {
  const { t } = useLanguage();
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(1);
  const [width, setWidth] = useState(500);
  const [zoom, setZoom] = useState(1);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [rendering, setRendering] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(Math.max(180, Math.floor(entries[0].contentRect.width))));
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    let cancelled = false;
    // Only supplied bytes are parsed. Scripting, attachments and interactive annotations are never enabled.
    const loading = getDocument({ data: data.slice(), stopAtErrors: true, maxImageSize: 16_000_000, useWasm: false, enableXfa: false });
    const timeout = window.setTimeout(() => { if (!cancelled) { setError(t('This PDF could not be previewed. Download the report to open it in your PDF reader.')); void loading.destroy(); } }, 15000);
    void loading.promise.then(document => {
      clearTimeout(timeout);
      if (cancelled) return;
      if (document.numPages > 100) { setError(t('This PDF has too many pages for an in-page preview. Download it to view the full report.')); void loading.destroy(); return; }
      setPdf(document);
    }).catch(() => { if (!cancelled) setError(t('This PDF could not be previewed. Download the report to open it in your PDF reader.')); });
    return () => { cancelled = true; clearTimeout(timeout); void loading.destroy(); };
  }, [data]);
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    let task: RenderTask | undefined;
    setRendering(true); setText('');
    void pdf.getPage(page).then(async sheet => {
      if (cancelled || !canvas.current) return;
      const natural = sheet.getViewport({ scale: 1 });
      const viewport = sheet.getViewport({ scale: (width / natural.width) * zoom });
      const density = Math.min(window.devicePixelRatio || 1, 2);
      const element = canvas.current;
      element.width = Math.ceil(viewport.width * density);
      element.height = Math.ceil(viewport.height * density);
      element.style.width = `${viewport.width}px`;
      element.style.height = `${viewport.height}px`;
      task = sheet.render({ canvas: element, viewport, transform: density === 1 ? undefined : [density, 0, 0, density, 0, 0], annotationMode: AnnotationMode.DISABLE });
      await task.promise;
      const content = await sheet.getTextContent();
      if (!cancelled) { setText(content.items.map(item => 'str' in item ? item.str : '').join(' ')); setRendering(false); }
    }).catch(() => { if (!cancelled) { setRendering(false); setError(t('This PDF could not be previewed. Download the report to open it in your PDF reader.')); } });
    return () => { cancelled = true; task?.cancel(); };
  }, [pdf, page, width, zoom]);
  return <div ref={container} className="min-w-0 space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><button type="button" className="btn-secondary px-3 text-sm" disabled={!pdf || page <= 1} onClick={() => setPage(v => v - 1)} aria-label={t('Previous page')}>‹</button><span className="text-xs text-slate-500"><I18nText text="Page" /> {page} / {pdf?.numPages || '…'}</span><button type="button" className="btn-secondary px-3 text-sm" disabled={!pdf || page >= pdf.numPages} onClick={() => setPage(v => v + 1)} aria-label={t('Next page')}>›</button></div><label className="flex items-center gap-2 text-xs text-slate-500"><I18nText text="Zoom" /><select className="input-field min-h-9 py-1 text-xs" value={zoom} onChange={e => setZoom(Number(e.target.value))}>{[1, 1.25, 1.5, 2].map(n => <option key={n} value={n}>{n * 100}%</option>)}</select></label></div>{error ? <p role="alert" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-950">{error}</p> : <>{(!pdf || rendering) && <p role="status" className="text-xs text-slate-500"><I18nText text="Loading PDF preview…" /></p>}<div className="max-h-[60dvh] overflow-x-auto overflow-y-auto rounded-lg border border-slate-200 bg-slate-100"><canvas key={`${page}-${width}-${zoom}`} ref={canvas} aria-label={t('PDF preview')} role="img" /></div><p className="sr-only">{text}</p></>}</div>;
}
