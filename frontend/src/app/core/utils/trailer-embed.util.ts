import { resolveMediaUrl } from './media-url.util';

/** Convierte URL de YouTube/Vimeo en URL embebible para iframe. */
export function trailerEmbedUrl(url: string | null | undefined): string | null {
  if (!url?.trim()) return null;
  const raw = url.trim();
  try {
    const u = new URL(raw);
    const host = u.hostname.replace(/^www\./, '');
    if (host === 'youtu.be') {
      const id = u.pathname.slice(1).split('/')[0];
      return id ? `https://www.youtube.com/embed/${id}?rel=0` : null;
    }
    if (host === 'youtube.com' || host === 'm.youtube.com') {
      if (u.pathname.startsWith('/embed/')) return raw;
      const id = u.searchParams.get('v');
      if (id) return `https://www.youtube.com/embed/${id}?rel=0`;
      const shorts = u.pathname.match(/^\/shorts\/([^/]+)/);
      if (shorts) return `https://www.youtube.com/embed/${shorts[1]}?rel=0`;
    }
    if (host === 'vimeo.com' || host === 'player.vimeo.com') {
      const id = u.pathname.split('/').filter(Boolean).pop();
      return id ? `https://player.vimeo.com/video/${id}` : null;
    }
  } catch {
    return null;
  }
  return null;
}

/** Video subido al servidor o archivo directo (mp4, webm…). */
export function trailerVideoSrc(url: string | null | undefined): string | null {
  if (!url?.trim()) return null;
  const raw = url.trim();
  if (/\.(mp4|webm|mov|m4v)(\?|#|$)/i.test(raw) || raw.includes('/uploads/videos/')) {
    return resolveMediaUrl(raw);
  }
  return null;
}
