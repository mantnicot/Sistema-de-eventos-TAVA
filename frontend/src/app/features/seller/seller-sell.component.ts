import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEvent, TavaEventDetail } from '../../core/models/event.model';
import { parseHttpError } from '../../core/utils/http-error.util';

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
  singleHolderMode = true;
  holderName = '';
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
    if (this.singleHolderMode) return;
    while (this.holderNames.length < q) this.holderNames.push('');
    if (this.holderNames.length > q) this.holderNames = this.holderNames.slice(0, q);
  }

  selectedType() {
    const ev = this.eventDetail();
    if (!ev || !this.selectedTypeId) return null;
    return ev.ticket_types.find((t) => t.id === this.selectedTypeId) ?? null;
  }

  totalPrice(): number {
    const tt = this.selectedType();
    return (tt?.price ?? 0) * this.quantity;
  }

  selling = false;

  vender(): void {
    if (this.selling) return;
    const ev = this.eventDetail();
    if (!ev || !this.selectedTypeId || !this.buyerEmail.trim()) {
      this.notify.warning('Datos', 'Completa evento, tipo de boleta y correo del comprador');
      return;
    }
    const names = this.singleHolderMode
      ? this.holderName.trim()
        ? [this.holderName.trim()]
        : []
      : this.holderNames.map((n) => n.trim()).filter(Boolean);
    if (this.singleHolderMode ? names.length !== 1 : names.length !== this.quantity) {
      this.notify.warning('Nombres', this.singleHolderMode ? 'Indica el nombre' : 'Indica el nombre de cada asistente');
      return;
    }

    const tt = this.selectedType();
    const total = this.totalPrice();
    this.notify.confirm(
      'Vender boletas',
      `Vas a registrar ${this.quantity} boleta(s) para "${ev.name}" por $${total.toLocaleString('es-CO')} COP. El comprador sera ${this.buyerEmail.trim()}.`,
      () => {
        if (this.selling) return;
        this.selling = true;
        this.notify.loadingTheatrical('Taquilla', 'purchase');
        this.api
          .post<{ message?: string; claim_code?: string | null }>('/tickets/sell', {
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
              this.notify.success(
                'Venta registrada',
                res.claim_code
                  ? `Código de reclamo: ${res.claim_code}. Las boletas quedaron listas y enviaremos el PDF al correo.`
                  : res.message ?? 'Las boletas quedaron listas y enviaremos el PDF al correo del comprador.'
              );
              this.buyerEmail = '';
              this.holderNames = [''];
              this.quantity = 1;
              this.onEventChange();
            },
            error: (err) => {
              this.selling = false;
              this.notify.hide();
              this.notify.showHttpError(parseHttpError(err, 'venta'));
            },
          });
      }
    );
  }
}
