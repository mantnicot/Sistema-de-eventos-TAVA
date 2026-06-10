import { TavaEvent, TavaEventDetail } from '../models/event.model';

export type EventPhase = 'upcoming' | 'live' | 'finished';

const BOGOTA_OFFSET = '-05:00';
const DEFAULT_DURATION_MIN = 120;

const FUNNY_CTAS = [
  '¡COMPRA YA!',
  'Regalo perfecto para la familia',
  'No te quedes sin butaca',
  'El telón se levanta pronto',
  'Trae a quien quieras impresionar',
  'Últimas boletas volando',
  'Esta noche puede ser legendaria',
];

const LIVE_MESSAGES = [
  '¡El telón ya se levantó! La gente lo está disfrutando en este momento.',
  'Función en curso — el público vive la magia del teatro ahora mismo.',
  '¡Evento en vivo! Las luces están encendidas y el escenario arde.',
];

export function formatEventTime(time: string): string {
  if (!time) return '';
  const parts = time.split(':');
  if (parts.length < 2) return time;
  const h = parseInt(parts[0], 10);
  const m = parts[1].slice(0, 2);
  const suffix = h >= 12 ? 'p. m.' : 'a. m.';
  const h12 = h % 12 || 12;
  return `${h12}:${m} ${suffix}`;
}

export function formatEventDateTime(date: string, time: string): string {
  if (!date) return formatEventTime(time);
  const d = new Date(`${date}T00:00:00${BOGOTA_OFFSET}`);
  const dateStr = d.toLocaleDateString('es-CO', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
  return `${dateStr} · ${formatEventTime(time)}`;
}

function durationMinutes(ev: TavaEvent): number {
  const mins = ev.theatrical_details?.duration_minutes;
  return mins && mins > 0 ? mins : DEFAULT_DURATION_MIN;
}

function parseEventStart(ev: TavaEvent): Date {
  const time = (ev.event_time || '19:00:00').slice(0, 8);
  return new Date(`${ev.event_date}T${time}${BOGOTA_OFFSET}`);
}

function parseEventEnd(ev: TavaEvent): Date {
  const start = parseEventStart(ev);
  return new Date(start.getTime() + durationMinutes(ev) * 60_000);
}

export function getEventPhase(ev: TavaEvent): EventPhase {
  if (ev.status === 'finalizado' || ev.status === 'cancelado') return 'finished';
  const now = Date.now();
  const end = parseEventEnd(ev).getTime();
  const start = parseEventStart(ev).getTime();
  if (now >= end) return 'finished';
  if (ev.status === 'en_curso' || now >= start) return 'live';
  return 'upcoming';
}

export function canPurchaseTickets(ev: TavaEvent): boolean {
  if (['cancelado', 'finalizado', 'borrador'].includes(ev.status)) return false;
  return getEventPhase(ev) === 'upcoming';
}

export function totalTicketsAvailable(ev: TavaEvent | TavaEventDetail): number {
  const detail = ev as TavaEventDetail;
  if (detail.ticket_types?.length) {
    return detail.ticket_types.reduce((sum, t) => sum + (t.quantity_available ?? 0), 0);
  }
  return (ev as TavaEvent & { tickets_available?: number }).tickets_available ?? 0;
}

export function funnyCtaForEvent(eventId: string): string {
  let hash = 0;
  for (let i = 0; i < eventId.length; i++) {
    hash = (hash + eventId.charCodeAt(i) * (i + 1)) % FUNNY_CTAS.length;
  }
  return FUNNY_CTAS[hash];
}

export function liveBannerMessage(eventId: string): string {
  let hash = 0;
  for (let i = 0; i < eventId.length; i++) {
    hash = (hash + eventId.charCodeAt(i)) % LIVE_MESSAGES.length;
  }
  return LIVE_MESSAGES[hash];
}

export function sortEventsByPriority<T extends TavaEvent>(events: T[]): T[] {
  const order: Record<EventPhase, number> = { live: 0, upcoming: 1, finished: 2 };
  return [...events].sort((a, b) => {
    const pa = order[getEventPhase(a)];
    const pb = order[getEventPhase(b)];
    if (pa !== pb) return pa - pb;
    return a.event_date.localeCompare(b.event_date);
  });
}

export function splitEventsByPhase<T extends TavaEvent>(events: T[]): {
  live: T[];
  upcoming: T[];
  finished: T[];
} {
  const live: T[] = [];
  const upcoming: T[] = [];
  const finished: T[] = [];
  for (const ev of events) {
    const phase = getEventPhase(ev);
    if (phase === 'live') live.push(ev);
    else if (phase === 'finished') finished.push(ev);
    else upcoming.push(ev);
  }
  return { live, upcoming, finished };
}
