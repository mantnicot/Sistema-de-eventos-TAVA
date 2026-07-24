import { Component, inject, OnInit, signal, ViewChild } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEvent, TavaEventDetail } from '../../core/models/event.model';
import { parseHttpError } from '../../core/utils/http-error.util';
import { TavaCaptchaComponent } from '../../shared/components/tava-captcha/tava-captcha.component';

@Component({
  selector: 'app-seller-sell',
  standalone: true,
  imports: [FormsModule, DecimalPipe, TavaCaptchaComponent],
  templateUrl: './seller-sell.component.html',
  styleUrl: './seller-sell.component.scss',
})
export class SellerSellComponent implements OnInit {
  @ViewChild(TavaCaptchaComponent) captcha?: TavaCaptchaComponent;
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
  captchaToken = '';

  ngOnInit(): void {
    this.notify.loadingTheatrical('Cargando eventos', 'loader');
    this.api.get<TavaEvent[]>('/events/assigned/mine', { staff_role: 'seller' }).subscribe({
      next: (e) => {
        this.notify.hide();
        this.events.set(e);
      },
      error: () => {
        this.notify.hide();
        this.events.set([]);
        this.notify.error('Eventos', 'No se pudieron cargar los eventos asignados.');
      },
    });
  }

  onEventChange(): void {
    this.selectedTypeId = '';
    this.eventDetail.set(null);
    if (!this.selectedEventId) return;
    this.notify.loadingTheatrical('Cargando evento', 'loader');
    this.api.get<TavaEventDetail>(`/events/${this.selectedEventId}`).subscribe({
      next: (d) => {
        this.notify.hide();
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
      error: () => {
        this.notify.hide();
        this.notify.error('Evento', 'No se pudo cargar el evento');
      },
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

  onCaptchaToken(token: string): void {
    this.captchaToken = token;
  }

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
    if (!this.captchaToken) {
      this.notify.warning('Verificación', 'Completa la verificación para registrar la venta.');
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
          .post<{ message?: string; claim_code?: string | null; email_sent?: boolean }>('/tickets/sell', {
            event_id: ev.id,
            ticket_type_id: this.selectedTypeId,
            quantity: this.quantity,
            buyer_email: this.buyerEmail.trim(),
            holder_names: names,
            legal_accepted: true,
            captcha_token: this.captchaToken,
          })
          .subscribe({
            next: (res) => {
              this.selling = false;
              this.notify.hide();
              if (res.email_sent) {
                this.notify.success(
                  'Boletas enviadas',
                  `El PDF y los códigos fueron enviados al correo del comprador.${res.claim_code ? ` Código de reclamo: ${res.claim_code}.` : ''}`
                );
              } else {
                this.notify.warning(
                  'Venta registrada',
                  `Las boletas se generaron, pero no pudimos confirmar el envío del correo.${res.claim_code ? ` Conserva el código de reclamo: ${res.claim_code}.` : ''}`
                );
              }
              this.buyerEmail = '';
              this.holderNames = [''];
              this.quantity = 1;
              this.captchaToken = '';
              this.captcha?.reset();
              this.onEventChange();
            },
            error: (err) => {
              this.selling = false;
              this.notify.hide();
              this.captchaToken = '';
              this.captcha?.reset();
              this.notify.showHttpError(parseHttpError(err, 'venta'));
            },
          });
      }
    );
  }
}
