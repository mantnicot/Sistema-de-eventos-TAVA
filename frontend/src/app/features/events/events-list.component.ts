import { Component, HostListener, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { TavaEvent } from '../../core/models/event.model';
import { readEventsCache, writeEventsCache } from '../../core/utils/events-cache.util';
import { onEventImageError } from '../../core/utils/event-image.util';
import {
  formatEventDateTime,
  formatEventTime,
  funnyCtaForEvent,
  getEventPhase,
  liveBannerMessage,
  splitEventsByPhase,
  totalTicketsAvailable,
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
  /** Activos = en vivo + próximos (carrusel). */
  readonly activeEvents = signal<TavaEvent[]>([]);
  readonly finishedEvents = signal<TavaEvent[]>([]);
  readonly activeIndex = signal(0);
  readonly loading = signal(false);
  readonly loadingStalled = signal(false);
  readonly loadError = signal<string | null>(null);
  search = '';
  category = '';
  readonly mediaUrl = resolveMediaUrl;
  readonly onImgError = onEventImageError;
  readonly formatEventDateTime = formatEventDateTime;
  readonly formatEventTime = formatEventTime;
  readonly funnyCta = funnyCtaForEvent;
  readonly liveMessage = liveBannerMessage;
  readonly getPhase = getEventPhase;
  readonly ticketsLeft = totalTicketsAvailable;
  private loadSub?: Subscription;
  private stallTimer: ReturnType<typeof setTimeout> | null = null;
  private autoplayTimer: ReturnType<typeof setInterval> | null = null;
  private readonly AUTOPLAY_MS = 6000;

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((q) => {
      this.search = q.get('search') ?? '';
      this.load();
    });
  }

  ngOnDestroy(): void {
    this.loadSub?.unsubscribe();
    this.clearStallTimer();
    this.stopAutoplay();
  }

  @HostListener('document:visibilitychange')
  onVisibility(): void {
    if (document.hidden) this.stopAutoplay();
    else this.startAutoplay();
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
          this.activeIndex.set(0);
          this.stopAutoplay();
        }
        this.loadError.set(
          'No pudimos cargar los eventos. Comprueba tu conexión e intenta de nuevo.'
        );
      },
    });
  }

  prevSlide(): void {
    const n = this.activeEvents().length;
    if (n < 2) return;
    this.activeIndex.set((this.activeIndex() - 1 + n) % n);
    this.restartAutoplay();
  }

  nextSlide(): void {
    const n = this.activeEvents().length;
    if (n < 2) return;
    this.activeIndex.set((this.activeIndex() + 1) % n);
    this.restartAutoplay();
  }

  goToSlide(i: number): void {
    if (i < 0 || i >= this.activeEvents().length) return;
    this.activeIndex.set(i);
    this.restartAutoplay();
  }

  private applyEvents(e: TavaEvent[]): void {
    this.events.set(e);
    const split = splitEventsByPhase(e);
    const active = [...split.live, ...split.upcoming];
    this.activeEvents.set(active);
    this.finishedEvents.set(split.finished);
    if (this.activeIndex() >= active.length) {
      this.activeIndex.set(0);
    }
    this.restartAutoplay();
  }

  private startAutoplay(): void {
    this.stopAutoplay();
    if (this.activeEvents().length < 2) return;
    this.autoplayTimer = setInterval(() => {
      const n = this.activeEvents().length;
      if (n < 2) return;
      this.activeIndex.set((this.activeIndex() + 1) % n);
    }, this.AUTOPLAY_MS);
  }

  private stopAutoplay(): void {
    if (this.autoplayTimer) {
      clearInterval(this.autoplayTimer);
      this.autoplayTimer = null;
    }
  }

  private restartAutoplay(): void {
    this.stopAutoplay();
    this.startAutoplay();
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
