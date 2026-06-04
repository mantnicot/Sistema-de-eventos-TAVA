import { environment } from '../../../environments/environment';

function apiMediaBase(): string {
  const env = environment as { apiUrl: string; mediaBaseUrl?: string };
  return env.mediaBaseUrl?.replace(/\/$/, '') || env.apiUrl.replace(/\/api\/v1\/?$/, '');
}

/** Convierte rutas /uploads/... en URL absoluta del API. */
export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return '/logo-tava.png';
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  const base = apiMediaBase();
  return `${base}${url.startsWith('/') ? url : `/${url}`}`;
}
