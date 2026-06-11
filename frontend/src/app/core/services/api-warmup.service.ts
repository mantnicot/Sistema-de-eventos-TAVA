import { Injectable, inject } from '@angular/core';
import { HttpBackend, HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/** Despierta la API en Render antes de peticiones pesadas. */
@Injectable({ providedIn: 'root' })
export class ApiWarmupService {
  private readonly http = new HttpClient(inject(HttpBackend));
  private inflight: Promise<boolean> | null = null;

  private healthUrl(): string {
    const base = environment.mediaBaseUrl || environment.apiUrl.replace(/\/api\/v1\/?$/, '');
    return `${base.replace(/\/$/, '')}/health`;
  }

  wake(): Promise<boolean> {
    if (this.inflight) return this.inflight;
    this.inflight = new Promise((resolve) => {
      this.http.get(this.healthUrl(), { responseType: 'text' }).subscribe({
        next: () => {
          this.inflight = null;
          resolve(true);
        },
        error: () => {
          this.inflight = null;
          resolve(false);
        },
      });
    });
    return this.inflight;
  }
}
