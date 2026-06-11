import { Component, inject, OnInit, signal, ViewChild } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEventDetail } from '../../core/models/event.model';
import {
  canPurchaseTickets,
  formatEventDateTime,
  formatEventTime,
  funnyCtaForEvent,
  getEventPhase,
  liveBannerMessage,
  totalTicketsAvailable,
} from '../../core/utils/event-timing.util';
import { mediaBackgroundStyle, resolveMediaUrl } from '../../core/utils/media-url.util';
import { trailerEmbedUrl, trailerVideoSrc } from '../../core/utils/trailer-embed.util';
import { onEventImageError } from '../../core/utils/event-image.util';
import { TavaTheatricalVideoComponent } from '../../shared/components/tava-theatrical-video/tava-theatrical-video.component';
import { TavaTicketPreviewComponent } from '../../shared/components/tava-ticket-preview/tava-ticket-preview.component';
import { TavaCaptchaComponent } from '../../shared/components/tava-captcha/tava-captcha.component';
import { TavaTheatricalLoaderComponent } from '../../shared/components/tava-theatrical-loader/tava-theatrical-loader.component';
import { SeatMapResponse } from '../../core/models/seating.model';
import {
  clearPurchaseDraft,
  readPurchaseDraft,
  savePurchaseDraft,
} from '../../core/utils/purchase-draft.util';
import { TavaSeatMapComponent } from '../../shared/components/tava-seat-map/tava-seat-map.component';
import { ApiWarmupService } from '../../core/services/api-warmup.service';

@Component({
  selector: 'app-event-detail',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    DecimalPipe,
    TavaTheatricalVideoComponent,
    TavaTicketPreviewComponent,
    TavaCaptchaComponent,
    TavaTheatricalLoaderComponent,
    TavaSeatMapComponent,
  ],
  templateUrl: './event-detail.component.html',
  styleUrl: './event-detail.component.scss',
})
export class EventDetailComponent implements OnInit {
  @ViewChild(TavaCaptchaComponent) captcha?: TavaCaptchaComponent;
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly warmup = inject(ApiWarmupService);
  readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly sanitizer = inject(DomSanitizer);
  readonly event = signal<TavaEventDetail | null>(null);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly seating = signal<SeatMapResponse | null>(null);
  selectedSeatIds: string[] = [];
  readonly selectedTypeId = signal<string | null>(null);
  readonly mediaUrl = resolveMediaUrl;
  readonly mediaBg = mediaBackgroundStyle;
  readonly trailerVideo = trailerVideoSrc;
  purchasing = false;
  captchaToken = '';

  readonly formatEventDateTime = formatEventDateTime;
  readonly formatEventTime = formatEventTime;
  readonly funnyCta = funnyCtaForEvent;
  readonly liveMessage = liveBannerMessage;
  readonly getPhase = getEventPhase;
  readonly canBuy = canPurchaseTickets;
  readonly ticketsLeft = totalTicketsAvailable;

  readonly onImgError = onEventImageError;

  seatingActive(): boolean {
    return Boolean(this.seating()?.enabled && this.seating()?.config?.enabled);
  }

  onSeatsChange(ids: string[]): void {
    this.selectedSeatIds = ids;
    this.quantity = ids.length || 1;
    if (!this.singleHolderMode) this.onQuantityChange();
  }

  private persistDraft(): void {
    const ev = this.event();
    if (!ev) return;
    savePurchaseDraft({
      eventId: ev.id,
      selectedTypeId: this.selectedTypeId(),
      quantity: this.quantity,
      singleHolderMode: this.singleHolderMode,
      holderName: this.holderName,
      holderNames: [...this.holderNames],
      legalAccepted: this.legalAccepted,
      selectedSeatIds: [...this.selectedSeatIds],
    });
  }

  private restoreDraft(eventId: string): void {
    const draft = readPurchaseDraft(eventId);
    if (!draft) return;
    if (draft.selectedTypeId) this.selectedTypeId.set(draft.selectedTypeId);
    this.quantity = draft.quantity;
    this.singleHolderMode = draft.singleHolderMode;
    this.holderName = draft.holderName;
    this.holderNames = [...draft.holderNames];
    this.legalAccepted = draft.legalAccepted;
    this.selectedSeatIds = [...draft.selectedSeatIds];
  }

  private loadSeating(eventId: string): void {
    this.api.get<SeatMapResponse>(`/events/${eventId}/seating`).subscribe({
      next: (map) => this.seating.set(map),
      error: () => this.seating.set({ enabled: false, config: null, seats: [] }),
    });
  }

  safeTrailer(url: string | undefined): SafeResourceUrl | null {
    const embed = trailerEmbedUrl(url);
    return embed ? this.sanitizer.bypassSecurityTrustResourceUrl(embed) : null;
  }

  quantity = 1;
  singleHolderMode = true;
  holderName = '';
  holderNames: string[] = [''];
  legalAccepted = false;

  selectedTicketType() {
    const ev = this.event();
    const id = this.selectedTypeId();
    if (!ev || !id) return null;
    return ev.ticket_types.find((t) => t.id === id) ?? null;
  }

  totalPrice(): number {
    const tt = this.selectedTicketType();
    return (tt?.price ?? 0) * this.quantity;
  }

  previewHolderName(): string {
    if (this.singleHolderMode) {
      return this.holderName.trim() || this.auth.user()?.full_name || 'Tu nombre';
    }
    return this.holderNames[0]?.trim() || this.auth.user()?.full_name || 'Tu nombre';
  }

  ngOnInit(): void {
    this.holderName = this.auth.user()?.full_name ?? '';
    this.loadEvent();
  }

  loadEvent(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.loading.set(false);
      this.loadError.set('Evento no encontrado.');
      return;
    }
    this.loading.set(true);
    this.loadError.set(null);
    this.event.set(null);

    void this.warmup.wake().finally(() => {
      this.api.get<TavaEventDetail>(`/events/${id}`).subscribe({
        next: (e) => {
          const detail: TavaEventDetail = {
            ...e,
            gallery: e.gallery ?? [],
            ticket_types: e.ticket_types ?? [],
          };
          this.event.set(detail);
          this.loading.set(false);
          if (detail.ticket_types.length) {
            this.selectedTypeId.set(detail.ticket_types[0].id);
          }
          this.restoreDraft(id);
          this.loadSeating(id);
        },
        error: () => {
          this.loading.set(false);
          this.loadError.set(
            'No pudimos cargar este evento. El servidor puede estar despertando — intenta de nuevo.'
          );
        },
      });
    });
  }

  onQuantityChange(): void {
    const q = Math.max(1, Math.min(20, this.quantity || 1));
    this.quantity = q;
    if (this.singleHolderMode) return;
    const defaultName = this.auth.user()?.full_name ?? '';
    while (this.holderNames.length < q) {
      this.holderNames.push(this.holderNames.length === 0 ? defaultName : '');
    }
    if (this.holderNames.length > q) this.holderNames = this.holderNames.slice(0, q);
  }

  onHolderModeChange(): void {
    if (this.singleHolderMode) return;
    this.onQuantityChange();
  }

  private resolveHolderNames(): string[] | null {
    if (this.singleHolderMode) {
      const name = this.holderName.trim();
      if (!name) return null;
      return [name];
    }
    const names = this.holderNames.map((n) => n.trim()).filter(Boolean);
    if (names.length !== this.quantity) return null;
    return names;
  }

  onCaptchaToken(token: string): void {
    this.captchaToken = token;
  }

  comprar(): void {
    if (!this.auth.isLoggedIn()) {
      this.persistDraft();
      this.notify.warning(
        'Inicia sesión',
        'Guardamos tu selección. Regístrate o ingresa para continuar la compra.'
      );
      this.router.navigate(['/registro'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    if (!this.legalAccepted) {
      this.notify.warning('Términos', 'Debes marcar la casilla de términos y condiciones para poder comprar');
      return;
    }
    const ev = this.event();
    const typeId = this.selectedTypeId();
    const tt = this.selectedTicketType();
    if (!ev || !typeId || !tt) return;

    if (!this.canBuy(ev)) {
      this.notify.warning('Evento finalizado', 'Te perdiste este evento, pero tenemos otros para ti.');
      return;
    }

    if (!this.captchaToken) {
      this.notify.warning('Verificación', 'Completa el puzzle de verificación antes de comprar');
      return;
    }

    if (this.seatingActive()) {
      if (this.selectedSeatIds.length !== this.quantity) {
        this.notify.warning('Sillas', 'Selecciona una silla por cada boleta en el mapa');
        return;
      }
    }

    const names = this.resolveHolderNames();
    if (!names) {
      this.notify.warning(
        'Nombres',
        this.singleHolderMode
          ? 'Indica el nombre para las boletas'
          : 'Indica el nombre de cada asistente'
      );
      return;
    }

    if (this.purchasing) return;

    const total = this.totalPrice();
    const confirmMsg =
      `Su compra sería boletas para el evento «${ev.name}», ` +
      `con la cantidad de ${this.quantity} boleta(s), ` +
      `por un valor de $${total.toLocaleString('es-CO')} COP.`;

    this.notify.confirm('Confirmar compra', confirmMsg, () => {
      if (this.purchasing) return;
      this.purchasing = true;
      this.notify.loadingTheatrical('Enviando boletas', 'purchase');
      this.api
        .post<{
          message?: string;
          payment_required?: boolean;
          checkout_url?: string;
          order_id?: string;
        }>('/tickets/purchase', {
          event_id: ev.id,
          ticket_type_id: typeId,
          quantity: this.quantity,
          holder_names: names,
          legal_accepted: true,
          captcha_token: this.captchaToken,
          seat_ids: this.seatingActive() ? this.selectedSeatIds : undefined,
        })
        .subscribe({
          next: (res) => {
            this.purchasing = false;
            this.notify.hide();
            clearPurchaseDraft();
            this.captcha?.reset();
            this.captchaToken = '';
            if (res.payment_required && res.checkout_url) {
              window.location.href = res.checkout_url;
              return;
            }
            this.notify.celebration(
              '¡Compra exitosa!',
              res.message ?? 'Tus boletas fueron generadas y enviadas a tu correo electrónico.'
            );
            setTimeout(() => {
              this.notify.hide();
              this.router.navigate(['/perfil']);
            }, 4500);
          },
          error: (err) => {
            this.purchasing = false;
            this.notify.hide();
            this.captcha?.reset();
            this.captchaToken = '';
            const msg = err?.error?.detail ?? 'No se pudo completar la compra';
            this.notify.error('Compra', typeof msg === 'string' ? msg : 'Error en la compra');
          },
        });
    });
  }
}
