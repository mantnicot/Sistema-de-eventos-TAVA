import { SiteAppearance } from '../services/site-settings.service';

const CACHE_KEY = 'tava_appearance_cache_v1';

export function readAppearanceCache(): SiteAppearance | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SiteAppearance;
    if (typeof parsed.loader_video_enabled !== 'boolean') return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeAppearanceCache(data: SiteAppearance): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
  } catch {
    /* quota or private mode */
  }
}
