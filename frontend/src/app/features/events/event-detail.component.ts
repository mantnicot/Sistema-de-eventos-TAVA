import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEventDetail } from '../../core/models/event.model';

@Component({
  selector: 'app-event-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, DecimalPipe],
  templateUrl: './event-detail.component.html',
  styleUrl: './event-detail.component.scss',
})
export class EventDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  readonly event = signal<TavaEventDetail | null>(null);
  readonly selectedTypeId = signal<string | null>(null);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.api.get<TavaEventDetail>(`/events/${id}`).subscribe({
        next: (e) => {
          this.event.set(e);
          if (e.ticket_types?.length) {
            this.selectedTypeId.set(e.ticket_types[0].id);
          }
        },
        error: () => this.notify.error('Evento', 'No se pudo cargar el evento'),
      });
    }
  }

  comprar(): void {
    if (!this.auth.isLoggedIn()) {
      this.notify.warning('Inicia sesión', 'Debes ingresar para comprar boletas');
      this.router.navigate(['/ingresar']);
      return;
    }
    const ev = this.event();
    const typeId = this.selectedTypeId();
    if (!ev || !typeId) return;

    this.notify.confirm('Comprar boletas', '¿Confirmas la compra de 1 boleta? (pago manual/demo)', () => {
      this.api
        .post<{ message?: string }>('/tickets/purchase', {
          event_id: ev.id,
          ticket_type_id: typeId,
          quantity: 1,
          legal_accepted: true,
          captcha_token: 'dev-captcha',
        })
        .subscribe({
          next: () => {
            this.notify.success('Compra', 'Boleta generada. Revisa tu perfil.');
            this.router.navigate(['/perfil']);
          },
          error: () => this.notify.error('Compra', 'No se pudo completar la compra'),
        });
    });
  }
}
