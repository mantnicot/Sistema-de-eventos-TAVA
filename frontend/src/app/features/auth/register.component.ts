import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { parseHttpError } from '../../core/utils/http-error.util';
import { randomTheatricalMessage } from '../../core/utils/theatrical-messages.util';

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
  theatricalLine = '';

  submit(): void {
    this.notify.loadingTheatrical('Registro', 'register');
    this.auth
      .register({ email: this.email, password: this.password, full_name: this.full_name, captcha_token: 'dev-captcha' })
      .subscribe({
        next: () => {
          this.notify.hide();
          this.pendingVerify = true;
          this.theatricalLine = randomTheatricalMessage('resend');
          this.notify.success(
            'Correo enviado',
            'Revisa tu bandeja: ahí está el enlace para activar tu cuenta.'
          );
        },
        error: (err) => {
          this.notify.hide();
          const parsed = parseHttpError(err, 'register');
          const emailFailed =
            parsed.code === 'REGISTER_FAILED' &&
            (parsed.message.toLowerCase().includes('correo') ||
              parsed.message.toLowerCase().includes('smtp'));
          if (emailFailed) {
            parsed.message =
              'Falló el envío del correo. Vamos revisando cómo solucionarlo; inténtalo de nuevo en un rato.';
            parsed.title = 'Correo no enviado';
          }
          this.notify.showHttpError(parsed);
        },
      });
  }
}
