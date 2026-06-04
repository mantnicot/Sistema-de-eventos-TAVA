import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { parseHttpError } from '../../core/utils/http-error.util';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './register.component.html',
  styleUrl: './auth-form.scss',
})
export class RegisterComponent {
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  email = '';
  password = '';
  full_name = '';
  pendingVerify = false;
  pendingMessage = '';
  verificationUrl: string | null = null;

  submit(): void {
    this.notify.loading('Registro', 'Creando tu cuenta...');
    this.auth
      .register({ email: this.email, password: this.password, full_name: this.full_name, captcha_token: 'dev-captcha' })
      .subscribe({
        next: (res) => {
          this.notify.hide();
          this.pendingVerify = true;
          this.pendingMessage = res.message;
          this.verificationUrl = res.verification_url ?? null;
          if (res.email_sent) {
            this.notify.success('Revisa tu correo', res.message);
          } else if (this.verificationUrl) {
            this.notify.warning('Verificación', 'Usa el enlace mostrado en pantalla');
          }
        },
        error: (err) => {
          this.notify.hide();
          const parsed = parseHttpError(err, 'register');
          this.notify.showHttpError(parsed);
        },
      });
  }

  copyLink(): void {
    if (!this.verificationUrl) return;
    navigator.clipboard.writeText(this.verificationUrl).then(() => {
      this.notify.success('Copiado', 'Enlace copiado al portapapeles');
    });
  }
}
