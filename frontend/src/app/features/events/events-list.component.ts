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
  readonly activeIndex = signal(0);
  readonly autoplayPaused = signal(false);
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
  private autoplayTimer: ReturnType<typeof setInterval> | null = null;
  private readonly AUTOPLAY_MS = 5500;

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
    else if (!this.autoplayPaused()) this.startAutoplay();
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

  prevSlide(event?: Event): void {
    event?.stopPropagation();
    event?.preventDefault();
    const n = this.activeEvents().length;
    if (n < 2) return;
    this.activeIndex.set((this.activeIndex() - 1 + n) % n);
    this.bumpAutoplay();
  }

  nextSlide(event?: Event): void {
    event?.stopPropagation();
    event?.preventDefault();
    const n = this.activeEvents().length;
    if (n < 2) return;
    this.activeIndex.set((this.activeIndex() + 1) % n);
    this.bumpAutoplay();
  }

  toggleAutoplay(event?: Event): void {
    event?.stopPropagation();
    event?.preventDefault();
    const paused = !this.autoplayPaused();
    this.autoplayPaused.set(paused);
    if (paused) this.stopAutoplay();
    else this.startAutoplay();
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
    this.bumpAutoplay();
  }

  private bumpAutoplay(): void {
    if (this.autoplayPaused()) {
      this.stopAutoplay();
      return;
    }
    this.restartAutoplay();
  }

  private startAutoplay(): void {
    this.stopAutoplay();
    if (this.autoplayPaused() || this.activeEvents().length < 2) return;
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
