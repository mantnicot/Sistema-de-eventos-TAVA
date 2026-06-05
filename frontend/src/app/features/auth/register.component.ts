import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TAVA_PRIVACY_CLAUSES, TAVA_PRIVACY_SUMMARY } from '../../core/constants/privacy-policy.const';
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

  readonly privacySummary = TAVA_PRIVACY_SUMMARY;
  readonly privacyClauses = TAVA_PRIVACY_CLAUSES;
  showLegal = false;

  email = '';
  password = '';
  full_name = '';
  phone = '';
  acceptPrivacy = false;
  acceptMarketing = false;
  pendingVerify = false;
  theatricalLine = '';

  submit(): void {
    if (!this.acceptPrivacy) {
      this.notify.warning('Datos personales', 'Debes aceptar el tratamiento de datos personales para registrarte.');
      return;
    }
    this.notify.loadingTheatrical('Registro', 'register');
    this.auth
      .register({
        email: this.email,
        password: this.password,
        full_name: this.full_name,
        phone: this.phone,
        accept_privacy_policy: this.acceptPrivacy,
        accept_marketing: this.acceptMarketing,
        captcha_token: 'dev-captcha',
      })
      .subscribe({
        next: () => {
          this.notify.hide();
          this.pendingVerify = true;
          this.theatricalLine = randomTheatricalMessage('resend');
          this.notify.success('Correo enviado', 'Revisa tu bandeja: ahí está el enlace para activar tu cuenta.');
        },
        error: (err) => {
          this.notify.hide();
          const parsed = parseHttpError(err, 'register');
          this.notify.showHttpError(parsed);
        },
      });
  }
}
