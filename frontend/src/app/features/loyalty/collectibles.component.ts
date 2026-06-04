import { Component, inject, OnInit, signal } from '@angular/core';
import { ApiService } from '../../core/services/api.service';

interface Collection {
  laminas: { event_id: string; lamina_url: string; earned_at: string }[];
  total: number;
  progress_to_free_ticket: number;
  events_required: number;
  free_ticket_available: boolean;
}

@Component({
  selector: 'app-collectibles',
  standalone: true,
  templateUrl: './collectibles.component.html',
  styleUrl: './collectibles.component.scss',
})
export class CollectiblesComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly collection = signal<Collection | null>(null);

  lockedCount(): number {
    const c = this.collection();
    if (!c) return 5;
    return Math.max(0, c.events_required - c.laminas.length);
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
