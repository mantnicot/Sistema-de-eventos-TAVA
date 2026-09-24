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

  /** URL del iframe (estable; no regenerar en cada CD o el mapa parpadea). */
  readonly mapsEmbedSrc = signal<SafeResourceUrl | null>(null);
  readonly mapsOpenHref = signal<string | null>(null);
  readonly venueLabel = signal('');

  private refreshMaps(ev: TavaEventDetail | null): void {
    if (!ev) {
      this.mapsEmbedSrc.set(null);
      this.mapsOpenHref.set(null);
      this.venueLabel.set('');
      return;
    }
    const city = (ev.city || '').trim();
    const address = (ev.address || '').trim();
    const label = [address, city].filter(Boolean).join(' · ') || city;
    this.venueLabel.set(label);

    // Sin dirección de calle el mapa solo muestra la ciudad entera; no embeber.
    if (!address) {
      this.mapsEmbedSrc.set(null);
      this.mapsOpenHref.set(
        city ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(city)}` : null
      );
      return;
    }

    const query = `${address}, ${city || 'Colombia'}`;
    const embed =
      `https://maps.google.com/maps?q=${encodeURIComponent(query)}&hl=es&z=16&ie=UTF8&output=embed`;
    this.mapsEmbedSrc.set(this.sanitizer.bypassSecurityTrustResourceUrl(embed));
    this.mapsOpenHref.set(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`);
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

  isFreeSale(ev: TavaEventDetail): boolean {
    return ev.theatrical_details?.sale_mode === 'free';
  }

  whatsappSaleLink(ev: TavaEventDetail): string {
    const phone = (ev.theatrical_details?.whatsapp_number ?? '').replace(/[^\d]/g, '');
    const configured = ev.theatrical_details?.whatsapp_message?.trim();
    const fallback =
      `Hola, vengo desde la página de TAVA Teatro.\n\n` +
      `Quiero boletas para: ${ev.name}\n` +
      `Fecha: ${ev.event_date} · Hora: ${this.formatEventTime(ev.event_time)}\n` +
      `Lugar: ${ev.city} · ${ev.address}`;
    const text = configured ? `${fallback}\n\n——— NOTA ——\n${configured}` : fallback;
    return `https://api.whatsapp.com/send?phone=${phone}&text=${encodeURIComponent(text)}`;
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
    this.refreshMaps(null);
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
        this.refreshMaps(detail);
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
    const free = this.isFreeSale(ev);
    const confirmMsg = free
      ? `Vas a reservar ${this.quantity} boleta(s) gratis para "${ev.name}". Se emitirán al instante.`
      : this.isWhatsAppSale(ev)
        ? `Vas a solicitar ${this.quantity} boleta(s) para "${ev.name}" por $${total.toLocaleString('es-CO')} COP. Se abrirá WhatsApp; la boleta se emite cuando validen tu pago.`
        : `Vas a comprar ${this.quantity} boleta(s) para "${ev.name}" ` +
          `por $${total.toLocaleString('es-CO')} COP. Revisa los nombres antes de continuar.`;

    this.notify.confirm(
      free ? 'Confirmar reserva' : this.isWhatsAppSale(ev) ? 'Continuar por WhatsApp' : 'Confirmar compra',
      confirmMsg,
      () => {
      if (this.purchasing) return;
      this.purchasing = true;
      this.notify.loadingTheatrical(free ? 'Reservando cupo' : 'Preparando compra', 'purchase');
      this.api
        .post<{
          message?: string;
          payment_required?: boolean;
          payment_channel?: string;
          checkout_url?: string;
          whatsapp_url?: string;
          whatsapp_message?: string;
          whatsapp_phone?: string;
          reservation?: boolean;
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
            if (res.payment_required && (res.whatsapp_url || res.whatsapp_message)) {
              const phone = (res.whatsapp_phone || '').replace(/[^\d]/g, '');
              const waUrl =
                res.whatsapp_message && phone
                  ? `https://api.whatsapp.com/send?phone=${phone}&text=${encodeURIComponent(res.whatsapp_message)}`
                  : res.whatsapp_url;
              if (waUrl) {
                window.open(waUrl, '_blank', 'noopener,noreferrer');
              }
              this.notify.celebration(
                'Solicitud creada',
                res.message ??
                  'Completa el pago por WhatsApp. Cuando el organizador valide el dinero, recibirás correo y código de boleta.'
              );
              return;
            }
            if (res.payment_required && res.checkout_url) {
              window.location.href = res.checkout_url;
              return;
            }
            this.notify.celebration(
              free || res.reservation ? '¡Reserva lista!' : '¡Compra lista!',
              res.message ??
                (free
                  ? 'Tu boleta gratis ya está disponible. El PDF también llegará a tu correo.'
                  : 'Tus boletas ya están disponibles. El PDF también llegará a tu correo.')
            );
            setTimeout(() => {
              this.notify.hide();
              this.router.navigate(['/perfil']);
            }, 4500);
          },
          error: (err) => {
            this.purchasing = false;
            this.notify.hide();
            this.notify.showHttpError(parseHttpError(err, free ? 'reserva' : 'compra'));
          },
        });
    });
  }
}
