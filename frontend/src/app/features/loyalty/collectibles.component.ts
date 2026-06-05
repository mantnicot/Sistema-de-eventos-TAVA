import { Component, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { TavaEvent, TheatricalDetails } from '../../core/models/event.model';
import { resolveMediaUrl } from '../../core/utils/media-url.util';

interface LaminaItem {
  event_id: string;
  lamina_url: string;
  earned_at: string;
  event?: TavaEvent & { theatrical_details?: TheatricalDetails };
}

interface Collection {
  laminas: LaminaItem[];
  total: number;
  progress_to_free_ticket: number;
  events_required: number;
  free_ticket_available: boolean;
}

@Component({
  selector: 'app-collectibles',
  standalone: true,
  imports: [DatePipe, RouterLink],
  templateUrl: './collectibles.component.html',
  styleUrl: './collectibles.component.scss',
})
export class CollectiblesComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly collection = signal<Collection | null>(null);
  readonly selectedLamina = signal<LaminaItem | null>(null);
  readonly mediaUrl = resolveMediaUrl;

  lockedCount(): number {
    const c = this.collection();
    if (!c) return 5;
    return Math.max(0, c.events_required - c.laminas.length);
  }

  openLamina(item: LaminaItem): void {
    this.selectedLamina.set(item);
  }

  closeModal(): void {
    this.selectedLamina.set(null);
  }

  ngOnInit(): void {
    this.api.get<Collection>('/loyalty/collection').subscribe({
      next: (c) => this.collection.set(c),
      error: () =>
        this.collection.set({
          laminas: [],
          total: 0,
          progress_to_free_ticket: 0,
          events_required: 5,
          free_ticket_available: false,
        }),
    });
  }
}
