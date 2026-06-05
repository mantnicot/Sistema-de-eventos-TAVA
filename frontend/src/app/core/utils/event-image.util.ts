/** Placeholder teatral cuando la imagen del evento no carga (p. ej. archivo perdido en Render). */
export const EVENT_IMAGE_PLACEHOLDER = '/placeholder-theater.svg';

/** true si la URL apunta a uploads locales del API (suelen 404 en Render tras redeploy). */
export function isStaleLocalUpload(url: string | null | undefined): boolean {
  if (!url?.trim()) return false;
  const u = url.trim();
  return (u.includes('/uploads/') || u.startsWith('/uploads/')) && !u.includes('cloudinary.com');
}

export function onEventImageError(ev: Event): void {
  const img = ev.target as HTMLImageElement;
  if (img.dataset['fallback'] === '1') return;
  img.dataset['fallback'] = '1';
  img.src = EVENT_IMAGE_PLACEHOLDER;
}
