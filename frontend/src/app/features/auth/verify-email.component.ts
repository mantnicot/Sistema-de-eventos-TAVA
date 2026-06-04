import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section class="auth-page">
      <div class="auth-form tava-card verify">
        <h1 class="tava-glow-text">Verificación de correo</h1>
        @if (loading()) {
          <p>Validando enlace…</p>
        } @else if (ok()) {
          <p class="ok">{{ message() }}</p>
          <a routerLink="/ingresar" class="tava-btn-primary">Ir a ingresar</a>
        } @else {
          <p class="err">{{ message() }}</p>
          <a routerLink="/ingresar" class="tava-btn-primary">Volver al login</a>
        }
      </div>
    </section>
  `,
  styleUrl: './auth-form.scss',
})
export class VerifyEmailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(true);
  readonly ok = signal(false);
  readonly message = signal('');

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.loading.set(false);
      this.message.set('Enlace inválido: falta el token.');
      return;
    }
    this.auth.verifyEmail(token).subscribe({
      next: (res) => {
        this.loading.set(false);
        this.ok.set(true);
        this.message.set(res.message);
        this.notify.success('Correo verificado', res.message);
      },
      error: () => {
        this.loading.set(false);
        this.message.set('El enlace no es válido o ya expiró. Solicita uno nuevo desde el login.');
      },
    });
  }
}
