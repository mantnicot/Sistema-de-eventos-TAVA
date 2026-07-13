import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, timeout } from 'rxjs';
import { environment } from '../../../environments/environment';

/** Despierta la API en Render antes de peticiones pesadas. */
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
    this.inflight = this.runWarmup().finally(() => {
      this.inflight = null;
    });
    return this.inflight;
  }

  private async runWarmup(): Promise<boolean> {
    const delays = [0, 2500, 6000];
    for (const waitMs of delays) {
      if (waitMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, waitMs));
      }
      if (await this.pingOnce()) return true;
    }
    return false;
  }

  private async pingOnce(): Promise<boolean> {
    try {
      await firstValueFrom(this.http.get(this.wakeUrl()).pipe(timeout(55000)));
      return true;
    } catch {
      return false;
    }
  }
}
