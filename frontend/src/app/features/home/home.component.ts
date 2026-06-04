import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';

interface Banner {
  id: string;
  title: string;
  image_url: string;
  link_url?: string;
}

interface FeaturedEvent {
  id: string;
  name: string;
  event_date: string;
  main_image_url?: string;
  category: string;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly banners = signal<Banner[]>([]);
  readonly featured = signal<FeaturedEvent[]>([]);

  ngOnInit(): void {
    this.api.get<Banner[]>('/marketing/banners').subscribe({
      next: (b) => this.banners.set(b),
      error: () => this.banners.set([]),
    });
    this.api.get<FeaturedEvent[]>('/marketing/carousel/destacados').subscribe({
      next: (e) => this.featured.set(e),
      error: () => this.featured.set([]),
    });
  }
}
