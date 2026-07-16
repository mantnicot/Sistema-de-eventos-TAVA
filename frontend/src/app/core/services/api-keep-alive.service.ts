import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { timeout } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_RETRY } from '../interceptors/retry.interceptor';

/** Intervalo < 15 min para evitar que Render (free) apague el servicio. */
const KEEP_ALIVE_INTERVAL_MS = 8 * 60 * 1000;

/**
 * Ping periódico mientras hay usuarios con la web abierta.
 * Complementa el cron de GitHub Actions (.github/workflows/api-keep-alive.yml).
 */
@Injectable({ providedIn: 'root' })
export class ApiKeepAliveService {
  private readonly http = inject(HttpClient);
  private timerId: ReturnType<typeof setInterval> | null = null;
  private started = false;

  private wakeUrl(): string {
    const base = environment.apiUrl.replace(/\/$/, '');
    return `${base}/ping`;
  }

  start(): void {
    if (this.started || !environment.production) return;
    this.started = true;
    this.timerId = setInterval(() => this.ping(), KEEP_ALIVE_INTERVAL_MS);

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.onVisibilityChange);
    }
  }

  stop(): void {
    if (this.timerId) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.onVisibilityChange);
    }
    this.started = false;
  }

  /** Ping ligero; ignora errores (solo mantiene tráfico hacia Render). */
  private readonly onVisibilityChange = (): void => {
    if (document.visibilityState === 'visible') {
      this.ping();
    }
  };

  private ping(): void {
    const ctx = new HttpContext().set(SKIP_RETRY, true);
    this.http
      .get(this.wakeUrl(), { context: ctx })
      .pipe(timeout(12000))
      .subscribe({ error: () => undefined });
  }
}
