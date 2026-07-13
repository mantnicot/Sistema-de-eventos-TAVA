import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TAVA_PRIVACY_CLAUSES, TAVA_PRIVACY_SUMMARY } from '../../core/constants/privacy-policy.const';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { parseHttpError } from '../../core/utils/http-error.util';
import { randomTheatricalMessage } from '../../core/utils/theatrical-messages.util';
import { TavaCaptchaComponent } from '../../shared/components/tava-captcha/tava-captcha.component';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [FormsModule, RouterLink, TavaCaptchaComponent],
  templateUrl: './register.component.html',
  styleUrl: './auth-form.scss',
})
export class RegisterComponent implements OnInit {
  @ViewChild(TavaCaptchaComponent) captcha?: TavaCaptchaComponent;
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly route = inject(ActivatedRoute);

  readonly returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/eventos';
  readonly loginQuery =
    this.returnUrl.startsWith('/') && this.returnUrl !== '/eventos'
      ? { returnUrl: this.returnUrl }
      : {};

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
  captchaToken = '';

  ngOnInit(): void {
    this.auth.preloadPublicKey();
  }

  onCaptchaToken(token: string): void {
    this.captchaToken = token;
  }

  submit(): void {
    if (!this.acceptPrivacy) {
      this.notify.warning('Datos personales', 'Debes aceptar el tratamiento de datos personales para registrarte.');
      return;
    }
    if (!this.captchaToken) {
      this.notify.warning('Verificación', 'Completa el puzzle de verificación antes de registrarte');
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
        captcha_token: this.captchaToken,
      })
      .subscribe({
        next: () => {
          this.notify.hide();
          this.captcha?.reset();
          this.captchaToken = '';
          this.pendingVerify = true;
          this.theatricalLine = randomTheatricalMessage('resend');
          this.notify.success('Correo enviado', 'Revisa tu bandeja: ahí está el enlace para activar tu cuenta.');
        },
        error: (err) => {
          this.notify.hide();
          this.captcha?.reset();
          this.captchaToken = '';
          const parsed = parseHttpError(err, 'register');
          this.notify.showHttpError(parsed);
        },
      });
  }
}
