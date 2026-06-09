import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { parseHttpError } from '../../core/utils/http-error.util';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './forgot-password.component.html',
  styleUrl: './auth-form.scss',
})
export class ForgotPasswordComponent {
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  email = '';
  sent = false;
  sentMessage = '';
  notRegisteredHint = false;

  submit(): void {
    const email = this.email.trim().toLowerCase();
    if (!email) {
      this.notify.warning('Correo', 'Escribe tu correo registrado');
      return;
    }
    this.notify.loadingTheatrical('Recuperación', 'forgot');
    this.auth.forgotPassword(email).subscribe({
      next: (res) => {
        this.notify.hide();
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
        this.notify.showHttpError(parseHttpError(err, 'forgot-password'));
      },
    });
  }
}
