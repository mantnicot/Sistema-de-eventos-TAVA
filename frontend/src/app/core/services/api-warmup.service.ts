import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { firstValueFrom, timeout } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_RETRY } from '../interceptors/retry.interceptor';

/** Despierta la API antes de peticiones pesadas (no bloquea la UI). */
@Injectable({ providedIn: 'root' })
export class ApiWarmupService {
  private readonly http = inject(HttpClient);
  private inflight: Promise<boolean> | null = null;

  private wakeUrl(): string {
    const base = environment.apiUrl.replace(/\/$/, '');
    return `${base}/ping`;
  }

  wake(): Promise<boolean> {
    if (this.inflight) return this.inflight;
    this.inflight = this.pingOnce().finally(() => {
      this.inflight = null;
    });
    return this.inflight;
  }

  private async pingOnce(): Promise<boolean> {
    try {
      const ctx = new HttpContext().set(SKIP_RETRY, false);
      await firstValueFrom(
        this.http.get(this.wakeUrl(), { context: ctx }).pipe(timeout(25000))
      );
      return true;
    } catch {
      return false;
    }
  }
}
