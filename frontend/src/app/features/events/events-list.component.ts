import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { TavaEvent } from '../../core/models/event.model';
import { readEventsCache, writeEventsCache } from '../../core/utils/events-cache.util';
import { onEventImageError } from '../../core/utils/event-image.util';
import {
  formatEventDateTime,
  getEventPhase,
  splitEventsByPhase,
} from '../../core/utils/event-timing.util';
import { resolveMediaUrl } from '../../core/utils/media-url.util';
import { TavaTheatricalLoaderComponent } from '../../shared/components/tava-theatrical-loader/tava-theatrical-loader.component';

@Component({
  selector: 'app-events-list',
  standalone: true,
  imports: [RouterLink, FormsModule, TavaTheatricalLoaderComponent],
  templateUrl: './events-list.component.html',
  styleUrl: './events-list.component.scss',
})
export class EventsListComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  readonly events = signal<TavaEvent[]>([]);
  readonly activeEvents = signal<TavaEvent[]>([]);
  readonly finishedEvents = signal<TavaEvent[]>([]);
  readonly loading = signal(false);
  readonly loadingStalled = signal(false);
  readonly loadError = signal<string | null>(null);
  search = '';
  category = '';
  readonly mediaUrl = resolveMediaUrl;
  readonly onImgError = onEventImageError;
  readonly formatEventDateTime = formatEventDateTime;
  readonly getPhase = getEventPhase;
  private loadSub?: Subscription;
  private stallTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((q) => {
      this.search = q.get('search') ?? '';
      this.load();
    });
  }

  ngOnDestroy(): void {
    this.loadSub?.unsubscribe();
    this.clearStallTimer();
  }

  load(): void {
    this.loadSub?.unsubscribe();
    this.clearStallTimer();
    const params: Record<string, string> = {};
    if (this.search) params['search'] = this.search;
    if (this.category) params['category'] = this.category;

    const cached = readEventsCache(this.search, this.category);
    if (cached?.length) {
      this.applyEvents(cached);
      this.loading.set(false);
    } else {
      this.loading.set(true);
      this.startStallTimer();
    }
    this.loadError.set(null);

    this.loadSub = this.api.get<TavaEvent[]>('/events', params).subscribe({
      next: (e) => {
        this.clearStallTimer();
        this.loading.set(false);
        writeEventsCache(this.search, this.category, e);
        this.applyEvents(e);
      },
      error: () => {
        this.clearStallTimer();
        this.loading.set(false);
        if (!cached?.length) {
          this.events.set([]);
          this.activeEvents.set([]);
          this.finishedEvents.set([]);
        }
        this.loadError.set(
          'No pudimos cargar los eventos. Comprueba tu conexión e intenta de nuevo.'
        );
      },
    });
  }

  excerpt(text: string | undefined | null, max = 180): string {
    const raw = (text ?? '').replace(/\s+/g, ' ').trim();
    if (!raw) return 'Sin descripción disponible.';
    if (raw.length <= max) return raw;
    return `${raw.slice(0, max).trimEnd()}…`;
  }

  private applyEvents(e: TavaEvent[]): void {
    this.events.set(e);
    const split = splitEventsByPhase(e);
    this.activeEvents.set([...split.live, ...split.upcoming]);
    this.finishedEvents.set(split.finished);
  }

  private startStallTimer(): void {
    this.loadingStalled.set(false);
    this.stallTimer = setTimeout(() => {
      if (this.loading()) this.loadingStalled.set(true);
    }, 5000);
  }

  private clearStallTimer(): void {
    if (this.stallTimer) {
      clearTimeout(this.stallTimer);
      this.stallTimer = null;
    }
    this.loadingStalled.set(false);
  }
}
