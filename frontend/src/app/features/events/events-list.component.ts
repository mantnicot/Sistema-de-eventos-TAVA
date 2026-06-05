import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { TavaEvent } from '../../core/models/event.model';
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
  search = '';
  category = '';
  readonly mediaUrl = resolveMediaUrl;

  onImgError(ev: Event): void {
    const img = ev.target as HTMLImageElement;
    if (img.src.includes('logo-tava')) return;
    img.src = '/logo-tava.png';
  }

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
    this.api.get<TavaEvent[]>('/events', params).subscribe({
      next: (e) => this.events.set(e),
      error: () => this.events.set([]),
    });
  }
}
