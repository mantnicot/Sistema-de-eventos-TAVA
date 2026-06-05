const CHUNK_RELOAD_KEY = 'tava-chunk-reload';

/** Tras un deploy en Vercel, el navegador puede pedir chunks viejos; recarga una vez. */
export function setupChunkLoadRecovery(): void {
  if (typeof window === 'undefined') return;

  const shouldReload = (message: string) =>
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('ChunkLoadError') ||
    message.includes('Loading chunk') ||
    message.includes('dynamically imported module');

  const tryReload = () => {
    if (!sessionStorage.getItem(CHUNK_RELOAD_KEY)) {
      sessionStorage.setItem(CHUNK_RELOAD_KEY, '1');
      window.location.reload();
      return true;
    }
    sessionStorage.removeItem(CHUNK_RELOAD_KEY);
    return false;
  };

  window.addEventListener('unhandledrejection', (ev) => {
    const msg = String(ev.reason?.message ?? ev.reason ?? '');
    if (shouldReload(msg)) tryReload();
  });

  window.addEventListener(
    'error',
    (ev) => {
      const target = ev.target as HTMLElement | null;
      if (target?.tagName === 'SCRIPT') {
        if (tryReload()) ev.preventDefault();
      }
    },
    true
  );
}
