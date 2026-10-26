import { Component, inject, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { SiteSettingsService } from '../../core/services/site-settings.service';
import { parseHttpError } from '../../core/utils/http-error.util';
import { TavaCaptchaComponent } from '../../shared/components/tava-captcha/tava-captcha.component';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [FormsModule, RouterLink, TavaCaptchaComponent],
  templateUrl: './forgot-password.component.html',
  styleUrl: './auth-form.scss',
})
export class ForgotPasswordComponent {
  @ViewChild(TavaCaptchaComponent) captcha?: TavaCaptchaComponent;
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly site = inject(SiteSettingsService);
  get captchaRequired(): boolean {
    return this.site.captchaRequired();
  }

  email = '';
  sent = false;
  sentMessage = '';
  notRegisteredHint = false;
  captchaToken = '';

  onCaptchaToken(token: string): void {
    this.captchaToken = this.site.captchaRequired() && token !== 'captcha-disabled' ? token : '';
  }

  submit(): void {
    const email = this.email.trim().toLowerCase();
    if (!email) {
      this.notify.warning('Correo', 'Escribe tu correo registrado');
      return;
    }
    if (this.site.captchaRequired() && !this.captchaToken) {
      this.notify.warning('Verificación', 'Completa la verificación antes de solicitar el cambio de contraseña.');
      return;
    }
    this.notify.loadingTheatrical('Recuperación', 'forgot');
    const token = this.site.captchaRequired() ? this.captchaToken : '';
    this.auth.forgotPassword(email, token).subscribe({
      next: (res) => {
        this.notify.hide();
        if (this.site.captchaRequired()) {
          this.captcha?.reset();
          this.captchaToken = '';
        }
        this.sent = true;
        this.sentMessage = res.message;
        this.notRegisteredHint = res.email_sent === false;
        if (res.email_sent) {
          this.notify.success('Correo enviado', 'Revisa tu bandeja y la carpeta de spam.');
        } else {
          this.notify.warning(
            'Revisa el correo',
            'Ese correo podría no estar registrado en TAVA. Usa el mismo email con el que creaste la cuenta.'
          );
        }
      },
      error: (err) => {
        this.notify.hide();
        if (this.site.captchaRequired()) {
          this.captcha?.reset();
          this.captchaToken = '';
        }
        this.notify.showHttpError(parseHttpError(err, 'forgot-password'));
      },
    });
  }
}
