import { Injectable, computed, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';
import { readAppearanceCache, writeAppearanceCache } from '../utils/appearance-cache.util';
import { ApiService } from './api.service';

export interface SiteAppearance {
  loader_video_url: string;
  loader_video_enabled: boolean;
  captcha_enabled: boolean;
  login_notice: string;
  login_notice_enabled: boolean;
}

@Injectable({ providedIn: 'root' })
export class SiteSettingsService {
  private readonly api = inject(ApiService);
  private readonly cacheTtlMs = 5 * 60 * 1000;
  private loadedAt = 0;
  private loading = false;
  /** El captcha no se exige hasta que el servidor lo confirme. Un caché viejo no puede bloquear el ingreso. */
  readonly appearance = signal<SiteAppearance | null>(this.cachedWithoutCaptchaGate());
  readonly captchaRequired = computed(() => this.appearance()?.captcha_enabled === true);

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
          const normalized = {
            ...a,
            captcha_enabled: !!a.captcha_enabled,
            login_notice: a.login_notice ?? '',
            login_notice_enabled: !!a.login_notice_enabled,
          };
          this.appearance.set(normalized);
          writeAppearanceCache(normalized);
        },
        error: () => {
          this.loadedAt = Date.now();
          const current = this.appearance();
          this.appearance.set({
            loader_video_url: current?.loader_video_url ?? '',
            loader_video_enabled: current?.loader_video_enabled ?? true,
            captcha_enabled: false,
            login_notice: current?.login_notice ?? '',
            login_notice_enabled: !!current?.login_notice_enabled,
          });
        },
      });
  }

  private cachedWithoutCaptchaGate(): SiteAppearance | null {
    const cached = readAppearanceCache();
    if (!cached) return null;
    return { ...cached, captcha_enabled: false };
  }

  updateAppearance(data: SiteAppearance) {
    this.loadedAt = 0;
    writeAppearanceCache(data);
    return this.api.put<SiteAppearance>('/settings/appearance', data);
  }
}
