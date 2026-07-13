import { Injectable, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';
import { ApiService } from './api.service';

export interface SiteAppearance {
  hero_video_url: string;
  hero_video_enabled: boolean;
}

@Injectable({ providedIn: 'root' })
export class SiteSettingsService {
  private readonly api = inject(ApiService);
  private readonly cacheTtlMs = 5 * 60 * 1000;
  private loadedAt = 0;
  private loading = false;
  readonly appearance = signal<SiteAppearance | null>(null);

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
        },
        error: () => {
          this.loadedAt = Date.now();
          this.appearance.set({
            hero_video_url: '',
            hero_video_enabled: false,
          });
        },
      });
  }

  updateAppearance(data: SiteAppearance) {
    this.loadedAt = 0;
    return this.api.put<SiteAppearance>('/settings/appearance', data);
  }
}
