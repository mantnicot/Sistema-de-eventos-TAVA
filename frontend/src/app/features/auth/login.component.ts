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

  submit(): void {
    this.notify.loading('Ingresando', 'Validando credenciales...');
    this.auth.login(this.email, this.password, 'dev-captcha').subscribe({
      next: () => {
        this.notify.hide();
        this.notify.success('Bienvenido', 'Sesión iniciada correctamente');
        this.router.navigate(['/perfil']);
      },
      error: (err) => {
        this.notify.hide();
        const parsed = parseHttpError(err, 'login');
        console[parsed.kind === 'user' ? 'warn' : 'error'](parsed.logLine);
        this.notify.showHttpError(parsed);
      },
    });
  }
}
