import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { parseHttpError } from '../../core/utils/http-error.util';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './auth-form.scss',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  email = '';
  password = '';
  submitting = false;
  needsVerification = false;
  resending = false;

  submit(): void {
    if (this.submitting) return;
    this.submitting = true;
    this.notify.loadingTheatrical('Ingresando', 'login');
    this.auth.login(this.email, this.password, 'dev-captcha').subscribe({
      next: () => {
        this.submitting = false;
        this.notify.hide();
        this.notify.success('Bienvenido', 'Sesión iniciada correctamente');
        this.router.navigate(['/perfil']);
      },
      error: (err) => {
        this.submitting = false;
        this.notify.hide();
        const parsed = parseHttpError(err, 'login');
        this.needsVerification = parsed.code === 'EMAIL_NOT_VERIFIED';
        console[parsed.kind === 'user' ? 'warn' : 'error'](parsed.logLine);
        this.notify.showHttpError(parsed);
      },
    });
  }

  resendVerification(): void {
    if (!this.email) {
      this.notify.warning('Correo', 'Escribe tu correo en el formulario');
      return;
    }
    if (this.resending) return;
    this.resending = true;
    this.notify.loadingTheatrical('Reenviando', 'resend');
    this.auth.resendVerification(this.email).subscribe({
      next: () => {
        this.resending = false;
        this.notify.hide();
        this.notify.success(
          'Correo enviado',
          'Revisa tu bandeja: ahí está el enlace para activar tu cuenta.'
        );
      },
      error: (err) => {
        this.resending = false;
        this.notify.hide();
        const parsed = parseHttpError(err, 'resend');
        if (
          parsed.code === 'RESEND_FAILED' ||
          parsed.message.toLowerCase().includes('correo')
        ) {
          parsed.title = 'Correo no enviado';
          parsed.message =
            'Falló el envío del correo. Vamos revisando cómo solucionarlo; inténtalo de nuevo en un rato.';
        }
        this.notify.showHttpError(parsed);
      },
    });
  }
}
