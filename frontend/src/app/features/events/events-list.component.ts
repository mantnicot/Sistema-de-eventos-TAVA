import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { TavaEvent } from '../../core/models/event.model';

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
