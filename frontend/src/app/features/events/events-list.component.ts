import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { TavaEvent } from '../../core/models/event.model';
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

@Component({
  selector: 'app-events-list',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './events-list.component.html',
  styleUrl: './events-list.component.scss',
})
export class EventsListComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  readonly events = signal<TavaEvent[]>([]);
  readonly liveEvents = signal<TavaEvent[]>([]);
  readonly upcomingEvents = signal<TavaEvent[]>([]);
  readonly finishedEvents = signal<TavaEvent[]>([]);
  readonly loading = signal(false);
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

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((q) => {
      this.search = q.get('search') ?? '';
      this.load();
    });
  }

  load(): void {
    const params: Record<string, string> = {};
    if (this.search) params['search'] = this.search;
    if (this.category) params['category'] = this.category;
    this.loading.set(true);
    this.loadError.set(null);
    this.api.get<TavaEvent[]>('/events', params).subscribe({
      next: (e) => {
        this.loading.set(false);
        this.events.set(e);
        const split = splitEventsByPhase(e);
        this.liveEvents.set(split.live);
        this.upcomingEvents.set(split.upcoming);
        this.finishedEvents.set(split.finished);
      },
      error: () => {
        this.loading.set(false);
        this.events.set([]);
        this.liveEvents.set([]);
        this.upcomingEvents.set([]);
        this.finishedEvents.set([]);
        this.loadError.set(
          'No pudimos cargar los eventos. El servidor puede estar despertando — espera unos segundos e intenta de nuevo.'
        );
      },
    });
  }
}
