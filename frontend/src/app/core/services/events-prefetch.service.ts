import { Injectable, inject } from '@angular/core';
import { Subscription } from 'rxjs';
import { ApiService } from './api.service';
import { TavaEvent } from '../models/event.model';
import { writeEventsCache } from '../utils/events-cache.util';

/** Precarga la cartelera en segundo plano al abrir la app. */
@Injectable({ providedIn: 'root' })
export class EventsPrefetchService {
  private readonly api = inject(ApiService);
  private inflight: Subscription | null = null;

  prefetch(): void {
    if (this.inflight) return;
    this.inflight = this.api.get<TavaEvent[]>('/events').subscribe({
      next: (events) => writeEventsCache('', '', events ?? []),
      complete: () => {
        this.inflight = null;
      },
      error: () => {
        this.inflight = null;
      },
    });
  }
}
