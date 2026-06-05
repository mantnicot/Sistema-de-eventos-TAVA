import { environment } from '../../../environments/environment';

function apiMediaBase(): string {
  const env = environment as { apiUrl: string; mediaBaseUrl?: string };
  return env.mediaBaseUrl?.replace(/\/$/, '') || env.apiUrl.replace(/\/api\/v1\/?$/, '');
}

/** Convierte rutas /uploads/... o URLs absolutas en URL válida para mostrar. */
export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url?.trim()) return '/logo-tava.png';
  const raw = url.trim();

  if (raw.startsWith('blob:') || raw.startsWith('data:')) return raw;

  // Assets estáticos del frontend (seed / public)
  if (raw.startsWith('/assets/') || raw.startsWith('assets/')) {
    return raw.startsWith('/') ? raw : `/${raw}`;
  }

  if (raw.startsWith('http://') || raw.startsWith('https://')) {
    const uploadIdx = raw.indexOf('/uploads/');
    if (uploadIdx >= 0) {
      return `${apiMediaBase()}${raw.slice(uploadIdx)}`;
    }
    const assetsIdx = raw.indexOf('/assets/');
    if (assetsIdx >= 0) {
      return raw.slice(assetsIdx);
    }
    return raw;
  }

  if (raw.startsWith('/uploads/')) {
    return `${apiMediaBase()}${raw}`;
  }

  const base = apiMediaBase();
  return `${base}${raw.startsWith('/') ? raw : `/${raw}`}`;
}

/** URL segura para background-image en CSS. */
export function mediaBackgroundStyle(url: string | null | undefined): string {
  const resolved = resolveMediaUrl(url).replace(/"/g, '\\22');
  return `url("${resolved}")`;
}
