import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEvent, TavaEventDetail } from '../../core/models/event.model';

@Component({
  selector: 'app-seller-sell',
  standalone: true,
  imports: [FormsModule, DecimalPipe],
  templateUrl: './seller-sell.component.html',
  styleUrl: './seller-sell.component.scss',
})
export class SellerSellComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  readonly events = signal<TavaEvent[]>([]);
  readonly eventDetail = signal<TavaEventDetail | null>(null);

  selectedEventId = '';
  selectedTypeId = '';
  quantity = 1;
  buyerEmail = '';
  holderNames: string[] = [''];

  ngOnInit(): void {
    this.api.get<TavaEvent[]>('/events/assigned/mine', { staff_role: 'seller' }).subscribe({
      next: (e) => this.events.set(e),
      error: () => this.events.set([]),
    });
  }

  onEventChange(): void {
    this.selectedTypeId = '';
    this.eventDetail.set(null);
    if (!this.selectedEventId) return;
    this.api.get<TavaEventDetail>(`/events/${this.selectedEventId}`).subscribe({
      next: (d) => {
        const detail: TavaEventDetail = {
          ...d,
          gallery: d.gallery ?? [],
          ticket_types: d.ticket_types ?? [],
        };
        this.eventDetail.set(detail);
        if (detail.ticket_types.length) {
          this.selectedTypeId = detail.ticket_types[0].id;
        }
      },
      error: () => this.notify.error('Evento', 'No se pudo cargar el evento'),
    });
  }

  onQuantityChange(): void {
    const q = Math.max(1, Math.min(20, this.quantity || 1));
    this.quantity = q;
    while (this.holderNames.length < q) this.holderNames.push('');
    if (this.holderNames.length > q) this.holderNames = this.holderNames.slice(0, q);
  }

  selling = false;

  vender(): void {
    if (this.selling) return;
    const ev = this.eventDetail();
    if (!ev || !this.selectedTypeId || !this.buyerEmail.trim()) {
      this.notify.warning('Datos', 'Completa evento, tipo de boleta y correo del comprador');
      return;
    }
    const names = this.holderNames.map((n) => n.trim()).filter(Boolean);
    if (names.length !== this.quantity) {
      this.notify.warning('Nombres', 'Indica el nombre de cada asistente');
      return;
    }

    this.notify.confirm(
      'Vender boletas',
      `¿Confirmas la venta de ${this.quantity} boleta(s) a ${this.buyerEmail}?`,
      () => {
        if (this.selling) return;
        this.selling = true;
        this.notify.loadingTheatrical('Taquilla', 'purchase');
        this.api
          .post<{ message?: string }>('/tickets/sell', {
            event_id: ev.id,
            ticket_type_id: this.selectedTypeId,
            quantity: this.quantity,
            buyer_email: this.buyerEmail.trim(),
            holder_names: names,
            legal_accepted: true,
            captcha_token: 'dev-captcha',
          })
          .subscribe({
            next: (res) => {
              this.selling = false;
              this.notify.hide();
              this.notify.success('Venta', res.message ?? 'Boletas enviadas por correo');
              this.buyerEmail = '';
              this.holderNames = [''];
              this.quantity = 1;
              this.onEventChange();
            },
            error: (err) => {
              this.selling = false;
              this.notify.hide();
              const msg = err?.error?.detail ?? 'No se pudo completar la venta';
              this.notify.error('Venta', typeof msg === 'string' ? msg : 'Error en la venta');
            },
          });
      }
    );
  }
}
