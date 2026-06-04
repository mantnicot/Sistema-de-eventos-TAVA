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
  resendLink: string | null = null;

  submit(): void {
    if (this.submitting) return;
    this.submitting = true;
    this.notify.loading('Ingresando', 'Validando credenciales...');
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
    this.auth.resendVerification(this.email).subscribe({
      next: (r) => {
        this.resendLink = r.verification_url ?? null;
        if (r.email_sent) {
          this.notify.success('Verificación', r.message);
        } else if (this.resendLink) {
          this.notify.warning('Correo no enviado', 'Usa el enlace que aparece abajo');
        } else {
          this.notify.success('Verificación', r.message);
        }
      },
      error: () => this.notify.error('Correo', 'No se pudo reenviar el enlace'),
    });
  }
}
