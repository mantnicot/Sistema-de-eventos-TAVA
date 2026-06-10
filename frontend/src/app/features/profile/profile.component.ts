import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';
import { formatEventTime } from '../../core/utils/event-timing.util';

interface MyTicket {
  id: string;
  order_id: string;
  event_id: string;
  event_name: string;
  event_date: string;
  event_time: string;
  city: string;
  holder_name: string | null;
  ticket_type: string;
  price: number;
  ticket_code?: string | null;
  is_used: boolean;
  is_cancelled?: boolean;
  pdf_url: string;
}

interface TicketEventGroup {
  event_id: string;
  event_name: string;
  event_date: string;
  event_time: string;
  city: string;
  order_id: string;
  pdf_url: string;
  tickets: MyTicket[];
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
  readonly formatTime = formatEventTime;

  readonly groupedTickets = computed(() => {
    const map = new Map<string, TicketEventGroup>();
    for (const t of this.tickets()) {
      let group = map.get(t.event_id);
      if (!group) {
        group = {
          event_id: t.event_id,
          event_name: t.event_name,
          event_date: t.event_date,
          event_time: t.event_time,
          city: t.city,
          order_id: t.order_id,
          pdf_url: t.pdf_url,
          tickets: [],
        };
        map.set(t.event_id, group);
      }
      group.tickets.push(t);
    }
    return Array.from(map.values()).sort((a, b) => b.event_date.localeCompare(a.event_date));
  });

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

  ticketStatus(t: MyTicket): string {
    if (t.is_cancelled) return 'Cancelada';
    if (t.is_used) return 'Usada';
    return 'Válida';
  }

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
