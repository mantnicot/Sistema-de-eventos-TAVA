import { TavaEvent } from '../../core/models/event.model';

const CACHE_KEY = 'tava_events_cache_v1';
const CACHE_TTL_MS = 15 * 60 * 1000;

interface EventsCache {
  at: number;
  search: string;
  category: string;
  data: TavaEvent[];
}

export function readEventsCache(search: string, category: string): TavaEvent[] | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as EventsCache;
    if (Date.now() - parsed.at > CACHE_TTL_MS) return null;
    if (parsed.search !== search || parsed.category !== category) return null;
    return parsed.data;
  } catch {
    return null;
  }
}

export function writeEventsCache(search: string, category: string, data: TavaEvent[]): void {
  try {
    const payload: EventsCache = { at: Date.now(), search, category, data };
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(payload));
  } catch {
    /* quota or private mode */
  }
}
