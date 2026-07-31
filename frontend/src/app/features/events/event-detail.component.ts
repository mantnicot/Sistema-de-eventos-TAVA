import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEvent, TavaEventDetail } from '../../core/models/event.model';
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
import { readEventsCache } from '../../core/utils/events-cache.util';
import { TavaTheatricalVideoComponent } from '../../shared/components/tava-theatrical-video/tava-theatrical-video.component';
import { TavaTheatricalLoaderComponent } from '../../shared/components/tava-theatrical-loader/tava-theatrical-loader.component';
import {
  clearPurchaseDraft,
  readPurchaseDraft,
  savePurchaseDraft,
} from '../../core/utils/purchase-draft.util';
import { parseHttpError } from '../../core/utils/http-error.util';

@Component({
  selector: 'app-event-detail',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    DecimalPipe,
    TavaTheatricalVideoComponent,
    TavaTheatricalLoaderComponent,
  ],
  templateUrl: './event-detail.component.html',
  styleUrl: './event-detail.component.scss',
})
export class EventDetailComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly sanitizer = inject(DomSanitizer);
  readonly event = signal<TavaEventDetail | null>(null);
  readonly relatedEvents = signal<TavaEvent[]>([]);
  readonly loading = signal(true);
  readonly loadingStalled = signal(false);
  readonly loadError = signal<string | null>(null);
  readonly selectedTypeId = signal<string | null>(null);
  readonly mediaUrl = resolveMediaUrl;
  readonly mediaBg = mediaBackgroundStyle;
  readonly trailerVideo = trailerVideoSrc;
  purchasing = false;

  readonly formatEventDateTime = formatEventDateTime;
  readonly formatEventTime = formatEventTime;
  readonly funnyCta = funnyCtaForEvent;
  readonly liveMessage = liveBannerMessage;
  readonly getPhase = getEventPhase;
  readonly canBuy = canPurchaseTickets;
  readonly ticketsLeft = totalTicketsAvailable;

  readonly onImgError = onEventImageError;

  onTicketTypeChange(typeId: string): void {
    this.selectedTypeId.set(typeId);
    this.persistDraft();
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
  private eventSub?: Subscription;
  private stallTimer: ReturnType<typeof setTimeout> | null = null;

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

  isWhatsAppSale(ev: TavaEventDetail): boolean {
    return ev.theatrical_details?.sale_mode === 'whatsapp';
  }

  whatsappSaleLink(ev: TavaEventDetail): string {
    const phone = (ev.theatrical_details?.whatsapp_number ?? '').replace(/[^\d]/g, '');
    const configured = ev.theatrical_details?.whatsapp_message?.trim();
    const fallback =
      `Hola TAVA, quiero conseguir boletas para ${ev.name} ` +
      `del ${ev.event_date} a las ${this.formatEventTime(ev.event_time)}.`;
    return `https://wa.me/${phone}?text=${encodeURIComponent(configured || fallback)}`;
  }

  ngOnInit(): void {
    this.holderName = this.auth.user()?.full_name ?? '';
    this.route.paramMap.subscribe(() => this.loadEvent());
  }

  ngOnDestroy(): void {
    this.eventSub?.unsubscribe();
    this.clearStallTimer();
  }

  loadEvent(): void {
    this.eventSub?.unsubscribe();
    this.clearStallTimer();
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.loading.set(false);
      this.loadError.set('Evento no encontrado.');
      return;
    }
    this.loading.set(true);
    this.startStallTimer();
    this.loadError.set(null);
    this.event.set(null);
    this.relatedEvents.set([]);

    this.eventSub = this.api.get<TavaEventDetail>(`/events/${id}`).subscribe({
      next: (e) => {
        this.clearStallTimer();
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
        this.loadRelatedEvents(id);
      },
      error: () => {
        this.clearStallTimer();
        this.loading.set(false);
        this.loadError.set('No pudimos cargar este evento. Intenta de nuevo en unos segundos.');
      },
    });
  }

  private loadRelatedEvents(currentEventId: string): void {
    const pick = (events: TavaEvent[]) =>
      events.filter((item) => item.id !== currentEventId && this.canBuy(item)).slice(0, 6);

    const cached = readEventsCache('', '');
    if (cached?.length) {
      this.relatedEvents.set(pick(cached));
      return;
    }
    this.api.get<TavaEvent[]>('/events').subscribe({
      next: (events) => this.relatedEvents.set(pick(events ?? [])),
      error: () => this.relatedEvents.set([]),
    });
  }

  private startStallTimer(): void {
    this.loadingStalled.set(false);
    this.stallTimer = setTimeout(() => {
      if (this.loading()) this.loadingStalled.set(true);
    }, 5000);
  }

  private clearStallTimer(): void {
    if (this.stallTimer) {
      clearTimeout(this.stallTimer);
      this.stallTimer = null;
    }
    this.loadingStalled.set(false);
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

  comprar(): void {
    if (!this.auth.isLoggedIn()) {
      this.persistDraft();
      this.notify.warning(
        'Registro obligatorio',
        'Para comprar boletas debes registrarte sí o sí. Guardamos tu selección para que continúes después de validar tu correo.'
      );
      this.router.navigate(['/registro'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    if (!this.legalAccepted) {
      this.notify.warning('Términos', 'Acepta los términos y condiciones para proteger tu compra.');
      return;
    }
    const ev = this.event();
    const typeId = this.selectedTypeId();
    const tt = this.selectedTicketType();
    if (!ev || !typeId || !tt) return;

    if (!this.canBuy(ev)) {
      this.notify.warning('Evento finalizado', 'Esta función ya pasó. Puedes revisar otros eventos disponibles.');
      return;
    }

    const names = this.resolveHolderNames();
    if (!names) {
      this.notify.warning(
        'Nombres',
        this.singleHolderMode
          ? 'Escribe el nombre que aparecerá en las boletas.'
          : 'Escribe el nombre de cada asistente.'
      );
      return;
    }

    if (this.purchasing) return;

    const total = this.totalPrice();
    const confirmMsg =
      `Vas a comprar ${this.quantity} boleta(s) para "${ev.name}" ` +
      `por $${total.toLocaleString('es-CO')} COP. Revisa los nombres antes de continuar.`;

    this.notify.confirm('Confirmar compra', confirmMsg, () => {
      if (this.purchasing) return;
      this.purchasing = true;
      this.notify.loadingTheatrical('Preparando compra', 'purchase');
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
        })
        .subscribe({
          next: (res) => {
            this.purchasing = false;
            this.notify.hide();
            clearPurchaseDraft();
            if (res.payment_required && res.checkout_url) {
              window.location.href = res.checkout_url;
              return;
            }
            this.notify.celebration(
              '¡Compra lista!',
              res.message ?? 'Tus boletas ya están disponibles. El PDF también llegará a tu correo.'
            );
            setTimeout(() => {
              this.notify.hide();
              this.router.navigate(['/perfil']);
            }, 4500);
          },
          error: (err) => {
            this.purchasing = false;
            this.notify.hide();
            this.notify.showHttpError(parseHttpError(err, 'compra'));
          },
        });
    });
  }
}
