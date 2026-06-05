import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { resolveMediaUrl } from '../../core/utils/media-url.util';

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
  imports: [RouterLink, FormsModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  readonly featured = signal<FeaturedEvent[]>([]);
  searchQuery = '';

  readonly mediaUrl = resolveMediaUrl;

  onImgError(ev: Event): void {
    const img = ev.target as HTMLImageElement;
    if (img.src.includes('logo-tava')) return;
    img.src = '/logo-tava.png';
  }

  ngOnInit(): void {
    this.api.get<FeaturedEvent[]>('/marketing/carousel/destacados').subscribe({
      next: (e) => this.featured.set(e),
      error: () => this.featured.set([]),
    });
  }

  goSearch(ev: Event): void {
    ev.preventDefault();
    const q = this.searchQuery.trim();
    this.router.navigate(['/eventos'], { queryParams: q ? { search: q } : {} });
  }
}
