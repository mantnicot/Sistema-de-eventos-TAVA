import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

export interface TavaEvent {
  id: string;
  name: string;
  description: string;
  event_date: string;
  event_time: string;
  city: string;
  category: string;
  status: string;
  main_image_url?: string;
}

@Component({
  selector: 'app-events-list',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './events-list.component.html',
  styleUrl: './events-list.component.scss',
})
export class EventsListComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly events = signal<TavaEvent[]>([]);
  search = '';
  category = '';

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    const params: Record<string, string> = {};
    if (this.search) params['search'] = this.search;
    if (this.category) params['category'] = this.category;
    this.api.get<TavaEvent[]>('/events', params).subscribe({
      next: (e) => this.events.set(e),
      error: () => this.events.set([]),
    });
  }
}
