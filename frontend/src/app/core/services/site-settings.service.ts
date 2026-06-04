import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from './api.service';

export interface SiteAppearance {
  hero_video_url: string;
  hero_video_enabled: boolean;
}

@Injectable({ providedIn: 'root' })
export class SiteSettingsService {
  private readonly api = inject(ApiService);
  readonly appearance = signal<SiteAppearance | null>(null);

  loadAppearance(): void {
    this.api.get<SiteAppearance>('/settings/appearance').subscribe({
      next: (a) => this.appearance.set(a),
      error: () =>
        this.appearance.set({
          hero_video_url: '',
          hero_video_enabled: false,
        }),
    });
  }

  updateAppearance(data: SiteAppearance) {
    return this.api.put<SiteAppearance>('/settings/appearance', data);
  }
}
