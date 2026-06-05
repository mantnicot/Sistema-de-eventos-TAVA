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

  submit(): void {
    this.notify.loadingTheatrical('Recuperación', 'forgot');
    this.auth.forgotPassword(this.email).subscribe({
      next: () => {
        this.notify.hide();
        this.sent = true;
        this.notify.success('Correo enviado', 'Si el correo existe, recibirás el enlace en unos minutos.');
      },
      error: (err) => {
        this.notify.hide();
        this.notify.showHttpError(parseHttpError(err, 'forgot-password'));
      },
    });
  }
}
