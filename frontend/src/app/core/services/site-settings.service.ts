import { Injectable, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';
import { readAppearanceCache, writeAppearanceCache } from '../utils/appearance-cache.util';
import { ApiService } from './api.service';

export interface SiteAppearance {
  loader_video_url: string;
  loader_video_enabled: boolean;
}

@Injectable({ providedIn: 'root' })
export class SiteSettingsService {
  private readonly api = inject(ApiService);
  private readonly cacheTtlMs = 5 * 60 * 1000;
  private loadedAt = 0;
  private loading = false;
  readonly appearance = signal<SiteAppearance | null>(readAppearanceCache());

  loadAppearance(): void {
    if (this.loading) return;
    const cached = this.appearance();
    if (cached && Date.now() - this.loadedAt < this.cacheTtlMs) return;

    this.loading = true;
    this.api
      .get<SiteAppearance>('/settings/appearance')
      .pipe(finalize(() => (this.loading = false)))
      .subscribe({
        next: (a) => {
          this.loadedAt = Date.now();
          this.appearance.set(a);
          writeAppearanceCache(a);
        },
        error: () => {
          this.loadedAt = Date.now();
          if (!this.appearance()) {
            this.appearance.set({
              loader_video_url: '',
              loader_video_enabled: true,
            });
          }
        },
      });
  }

  updateAppearance(data: SiteAppearance) {
    this.loadedAt = 0;
    writeAppearanceCache(data);
    return this.api.put<SiteAppearance>('/settings/appearance', data);
  }
}
