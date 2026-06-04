import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEvent } from './events-list.component';

@Component({
  selector: 'app-event-detail',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './event-detail.component.html',
  styleUrl: './event-detail.component.scss',
})
export class EventDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  readonly event = signal<TavaEvent | null>(null);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.api.get<TavaEvent>(`/events/${id}`).subscribe({
        next: (e) => this.event.set(e),
        error: () => this.notify.error('Evento', 'No se pudo cargar el evento'),
      });
    }
  }

  comprar(): void {
    if (!this.auth.isLoggedIn()) {
      this.notify.warning('Inicia sesión', 'Debes ingresar para comprar boletas');
      return;
    }
    this.notify.confirm(
      'Comprar boletas',
      '¿Deseas continuar al proceso de compra? Se aplicará verificación captcha y términos legales.',
      () => this.notify.success('Compra', 'Flujo de compra listo — conecta pasarela de pago'),
    );
  }
}
