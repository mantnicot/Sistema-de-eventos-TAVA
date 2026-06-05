import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEventDetail } from '../../core/models/event.model';
import { resolveMediaUrl } from '../../core/utils/media-url.util';
import { trailerEmbedUrl } from '../../core/utils/trailer-embed.util';
import { TavaTicketPreviewComponent } from '../../shared/components/tava-ticket-preview/tava-ticket-preview.component';

@Component({
  selector: 'app-event-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, DecimalPipe, TavaTicketPreviewComponent],
  templateUrl: './event-detail.component.html',
  styleUrl: './event-detail.component.scss',
})
export class EventDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly sanitizer = inject(DomSanitizer);
  readonly event = signal<TavaEventDetail | null>(null);
  readonly selectedTypeId = signal<string | null>(null);
  readonly mediaUrl = resolveMediaUrl;

  safeTrailer(url: string | undefined): SafeResourceUrl | null {
    const embed = trailerEmbedUrl(url);
    return embed ? this.sanitizer.bypassSecurityTrustResourceUrl(embed) : null;
  }

  quantity = 1;
  holderNames: string[] = [''];
  legalAccepted = false;

  selectedTicketType() {
    const ev = this.event();
    const id = this.selectedTypeId();
    if (!ev || !id) return null;
    return ev.ticket_types.find((t) => t.id === id) ?? null;
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.api.get<TavaEventDetail>(`/events/${id}`).subscribe({
        next: (e) => {
          const detail: TavaEventDetail = {
            ...e,
            gallery: e.gallery ?? [],
            ticket_types: e.ticket_types ?? [],
          };
          this.event.set(detail);
          if (detail.ticket_types.length) {
            this.selectedTypeId.set(detail.ticket_types[0].id);
          }
        },
        error: () => this.notify.error('Evento', 'No se pudo cargar el evento'),
      });
    }
  }

  onQuantityChange(): void {
    const q = Math.max(1, Math.min(20, this.quantity || 1));
    this.quantity = q;
    const defaultName = this.auth.user()?.full_name ?? '';
    while (this.holderNames.length < q) {
      this.holderNames.push(this.holderNames.length === 0 ? defaultName : '');
    }
    if (this.holderNames.length > q) this.holderNames = this.holderNames.slice(0, q);
  }

  comprar(): void {
    if (!this.auth.isLoggedIn()) {
      this.notify.warning('Inicia sesión', 'Debes ingresar para comprar boletas');
      this.router.navigate(['/ingresar']);
      return;
    }
    if (!this.legalAccepted) {
      this.notify.warning('Términos', 'Debes aceptar los términos y condiciones');
      return;
    }
    const ev = this.event();
    const typeId = this.selectedTypeId();
    if (!ev || !typeId) return;

    const names = this.holderNames.map((n) => n.trim()).filter(Boolean);
    if (names.length !== this.quantity) {
      this.notify.warning('Nombres', 'Indica el nombre de cada asistente');
      return;
    }

    this.notify.confirm(
      'Comprar boletas',
      `¿Confirmas la compra de ${this.quantity} boleta(s)? Recibirás el PDF por correo.`,
      () => {
        this.notify.loadingTheatrical('Taquilla', 'purchase');
        this.api
          .post<{ message?: string }>('/tickets/purchase', {
            event_id: ev.id,
            ticket_type_id: typeId,
            quantity: this.quantity,
            holder_names: names,
            legal_accepted: true,
            captcha_token: 'dev-captcha',
          })
          .subscribe({
            next: (res) => {
              this.notify.hide();
              this.notify.success('Compra', res.message ?? 'Boletas generadas. Revisa tu correo.');
              this.router.navigate(['/perfil']);
            },
            error: (err) => {
              this.notify.hide();
              const msg = err?.error?.detail ?? 'No se pudo completar la compra';
              this.notify.error('Compra', typeof msg === 'string' ? msg : 'Error en la compra');
            },
          });
      }
    );
  }
}
