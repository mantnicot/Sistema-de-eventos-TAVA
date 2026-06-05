/** Placeholder teatral cuando la imagen del evento no carga (p. ej. archivo perdido en Render). */
export const EVENT_IMAGE_PLACEHOLDER = '/placeholder-theater.svg';

export function onEventImageError(ev: Event): void {
  const img = ev.target as HTMLImageElement;
  if (img.dataset['fallback'] === '1') return;
  img.dataset['fallback'] = '1';
  img.src = EVENT_IMAGE_PLACEHOLDER;
}
