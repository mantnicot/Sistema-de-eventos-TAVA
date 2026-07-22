import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';
import { formatEventTime } from '../../core/utils/event-timing.util';
import { TavaEvent, TavaEventDetail } from '../../core/models/event.model';

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

interface SellerTicket {
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
  claim_code?: string | null;
  created_at: string | null;
  pdf_url: string;
  order_pdf_url: string;
}

interface SellerEventGroup {
  event_id: string;
  event_name: string;
  event_date: string;
  event_time: string;
  city: string;
  tickets: SellerTicket[];
}

interface ClaimTicketsResponse {
  message: string;
  order_id: string;
  pdf_url: string;
  tickets_count: number;
}

interface AdminIssueResponse {
  message: string;
  order_id: string;
  claim_code: string;
  pdf_url: string;
  event_name: string;
  event_date: string;
  event_time: string;
  ticket_type: string;
  quantity: number;
  total: number;
  buyer_name: string;
  buyer_email: string;
}

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, FormsModule],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly notify = inject(NotificationService);
  readonly tickets = signal<MyTicket[]>([]);
  readonly sellerTickets = signal<SellerTicket[]>([]);
  readonly adminEvents = signal<TavaEvent[]>([]);
  readonly adminEventDetail = signal<TavaEventDetail | null>(null);
  readonly formatTime = formatEventTime;
  claimCode = '';
  claiming = false;
  adminEventId = '';
  adminTicketTypeId = '';
  adminQuantity = 1;
  adminBuyerName = '';
  adminBuyerEmail = '';
  adminIssuing = false;

  readonly groupedSellerTickets = computed(() => {
    const map = new Map<string, SellerEventGroup>();
    for (const t of this.sellerTickets()) {
      let group = map.get(t.event_id);
      if (!group) {
        group = {
          event_id: t.event_id,
          event_name: t.event_name,
          event_date: t.event_date,
          event_time: t.event_time,
          city: t.city,
          tickets: [],
        };
        map.set(t.event_id, group);
      }
      group.tickets.push(t);
    }
    return Array.from(map.values()).sort((a, b) => b.event_date.localeCompare(a.event_date));
  });

  readonly sellerTicketCount = computed(() => this.sellerTickets().length);

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
    this.loadTickets();
    if (this.auth.isSeller()) {
      this.loadSellerSales();
    }
    if (this.auth.isAdmin()) {
      this.loadAdminEvents();
    }
  }

  private loadTickets(): void {
    this.api.get<MyTicket[]>('/tickets/mine').subscribe({
      next: (t) => this.tickets.set(t),
      error: () => this.tickets.set([]),
    });
  }

  private loadSellerSales(): void {
    this.api.get<SellerTicket[]>('/tickets/seller/mine').subscribe({
      next: (s) => this.sellerTickets.set(s),
      error: () => this.sellerTickets.set([]),
    });
  }

  private loadAdminEvents(): void {
    this.api.get<TavaEvent[]>('/events/admin/all', { limit: 100 }).subscribe({
      next: (events) => this.adminEvents.set(events),
      error: () => this.adminEvents.set([]),
    });
  }

  onAdminEventChange(): void {
    this.adminTicketTypeId = '';
    this.adminEventDetail.set(null);
    if (!this.adminEventId) return;
    this.api.get<TavaEventDetail>(`/events/${this.adminEventId}`).subscribe({
      next: (event) => {
        const detail = {
          ...event,
          gallery: event.gallery ?? [],
          ticket_types: event.ticket_types ?? [],
        };
        this.adminEventDetail.set(detail);
        if (detail.ticket_types.length) {
          this.adminTicketTypeId = detail.ticket_types[0].id;
        }
      },
      error: () => this.notify.error('Evento', 'No se pudo cargar la informaciÃ³n del evento'),
    });
  }

  selectedAdminTicketType() {
    const event = this.adminEventDetail();
    if (!event || !this.adminTicketTypeId) return null;
    return event.ticket_types.find((t) => t.id === this.adminTicketTypeId) ?? null;
  }

  adminTotal(): number {
    return (this.selectedAdminTicketType()?.price ?? 0) * this.adminQuantity;
  }

  issueAdminTickets(): void {
    const event = this.adminEventDetail();
    const ticketType = this.selectedAdminTicketType();
    const buyerName = this.adminBuyerName.trim();
    const buyerEmail = this.adminBuyerEmail.trim();
    const quantity = Math.max(1, Math.min(20, this.adminQuantity || 1));
    this.adminQuantity = quantity;

    if (!event || !ticketType || !buyerName || !buyerEmail) {
      this.notify.warning('Datos incompletos', 'Selecciona evento, tipo, nombre y correo del comprador');
      return;
    }
    if (this.adminIssuing) return;

    const total = this.adminTotal();
    this.notify.confirm(
      'Emitir boletas',
      `Vas a generar ${quantity} boleta(s) para ${buyerName} por $${total.toLocaleString('es-CO')} COP. Se enviarÃ¡n al correo ${buyerEmail}.`,
      () => {
        if (this.adminIssuing) return;
        this.adminIssuing = true;
        this.notify.loadingTheatrical('Generando boletas', 'purchase');
        this.api
          .post<AdminIssueResponse>('/tickets/admin/issue-claim', {
            event_id: event.id,
            ticket_type_id: ticketType.id,
            quantity,
            buyer_name: buyerName,
            buyer_email: buyerEmail,
            holder_names: [buyerName],
          })
          .subscribe({
            next: (res) => {
              this.adminIssuing = false;
              this.notify.hide();
              this.notify.success(
                'Boletas enviadas',
                `CÃ³digo de reclamo: ${res.claim_code}. El comprador ya recibiÃ³ el PDF y el cÃ³digo por correo.`
              );
              this.adminBuyerName = '';
              this.adminBuyerEmail = '';
              this.adminQuantity = 1;
              this.onAdminEventChange();
              this.loadSellerSales();
            },
            error: (err) => {
              this.adminIssuing = false;
              this.notify.hide();
              const detail = err?.error?.detail || 'No se pudieron generar las boletas';
              this.notify.error('EmisiÃ³n fallida', detail);
            },
          });
      }
    );
  }

  claimTickets(): void {
    const code = this.claimCode.trim();
    if (!code) {
      this.notify.warning('Código', 'Escribe el código para reclamar tus boletas');
      return;
    }
    if (this.claiming) return;
    this.claiming = true;
    this.notify.loadingTheatrical('Reclamando boletas', 'purchase');
    this.api.post<ClaimTicketsResponse>('/tickets/claim-code', { code }).subscribe({
      next: (res) => {
        this.claiming = false;
        this.notify.hide();
        this.claimCode = '';
        this.notify.success('Boletas reclamadas', res.message);
        this.loadTickets();
      },
      error: (err) => {
        this.claiming = false;
        this.notify.hide();
        const detail = err?.error?.detail || 'No pudimos reclamar boletas con ese código';
        this.notify.error('Código no válido', detail);
      },
    });
  }

  ticketStatus(t: MyTicket | SellerTicket): string {
    if (t.is_cancelled) return 'Cancelada';
    if (t.is_used) return 'Usada';
    return 'Válida';
  }

  showClaimForTicket(tickets: SellerTicket[], index: number): boolean {
    const current = tickets[index];
    if (!current?.claim_code) return false;
    if (index === 0) return true;
    return current.order_id !== tickets[index - 1]?.order_id;
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
