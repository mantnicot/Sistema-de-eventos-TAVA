import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';
import { onEventImageError } from '../../core/utils/event-image.util';
import { resolveMediaUrl } from '../../core/utils/media-url.util';

interface MyTicket {
  id: string;
  order_id: string;
  event_id: string;
  event_name: string;
  event_date: string;
  event_time: string;
  city: string;
  address: string;
  holder_name: string | null;
  ticket_type: string;
  price: number;
  qr_token: string;
  is_used: boolean;
  main_image_url?: string;
  pdf_url: string;
}

interface SellerSale {
  order_id: string;
  event_name: string;
  total: number;
  quantity: number;
  created_at: string | null;
  pdf_url: string;
  holders: (string | null)[];
}

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly notify = inject(NotificationService);
  readonly tickets = signal<MyTicket[]>([]);
  readonly sellerSales = signal<SellerSale[]>([]);
  readonly mediaUrl = resolveMediaUrl;

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) return;
    this.api.get<MyTicket[]>('/tickets/mine').subscribe({
      next: (t) => this.tickets.set(t),
      error: () => this.tickets.set([]),
    });
    if (this.auth.isSeller()) {
      this.api.get<SellerSale[]>('/tickets/seller/mine').subscribe({
        next: (s) => this.sellerSales.set(s),
        error: () => this.sellerSales.set([]),
      });
    }
  }

  readonly onImgError = onEventImageError;

  downloadPdf(pdfUrl: string, label: string): void {
    this.api.downloadBlob(pdfUrl).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${label}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      },
      error: () => this.notify.error('PDF', 'No se pudo descargar el PDF'),
    });
  }
}
