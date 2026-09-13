import {
  Component,
  HostListener,
  inject,
  OnDestroy,
  OnInit,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { TavaEvent } from '../../core/models/event.model';
import { onEventImageError } from '../../core/utils/event-image.util';
import {
  formatEventDateTime,
  getEventPhase,
  splitEventsByPhase,
} from '../../core/utils/event-timing.util';
import { resolveMediaUrl } from '../../core/utils/media-url.util';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);
  readonly activeEvents = signal<TavaEvent[]>([]);
  readonly activeIndex = signal(0);
  readonly autoplayPaused = signal(false);
  searchQuery = '';

  readonly mediaUrl = resolveMediaUrl;
  readonly onImgError = onEventImageError;
  readonly formatEventDateTime = formatEventDateTime;
  readonly getPhase = getEventPhase;

  private autoplayTimer: ReturnType<typeof setInterval> | null = null;
  private readonly AUTOPLAY_MS = 5500;

  ngOnInit(): void {
    this.api.get<TavaEvent[]>('/events').subscribe({
      next: (events) => {
        const split = splitEventsByPhase(events);
        this.activeEvents.set([...split.live, ...split.upcoming]);
        this.activeIndex.set(0);
        this.bumpAutoplay();
      },
      error: () => this.activeEvents.set([]),
    });
  }

  ngOnDestroy(): void {
    this.stopAutoplay();
  }

  @HostListener('document:visibilitychange')
  onVisibility(): void {
    if (document.hidden) this.stopAutoplay();
    else if (!this.autoplayPaused()) this.startAutoplay();
  }

  goSearch(ev: Event): void {
    ev.preventDefault();
    const q = this.searchQuery.trim();
    this.router.navigate(['/eventos'], { queryParams: q ? { search: q } : {} });
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
}
