import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
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
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  email = '';
  password = '';
  full_name = '';

  submit(): void {
    this.notify.loading('Registro', 'Creando tu cuenta...');
    this.auth
      .register({ email: this.email, password: this.password, full_name: this.full_name, captcha_token: 'dev-captcha' })
      .subscribe({
        next: () => {
          this.notify.hide();
          this.notify.success('¡Bienvenido a TAVA!', 'Tu cuenta fue creada');
          this.router.navigate(['/perfil']);
        },
        error: (err) => {
          this.notify.hide();
          const parsed = parseHttpError(err, 'register');
          console[parsed.kind === 'user' ? 'warn' : 'error'](parsed.logLine);
          this.notify.showHttpError(parsed);
        },
      });
  }
}
