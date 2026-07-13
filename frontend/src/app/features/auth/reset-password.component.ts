import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { parseHttpError } from '../../core/utils/http-error.util';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './reset-password.component.html',
  styleUrl: './auth-form.scss',
})
export class ResetPasswordComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  token = '';
  password = '';
  password2 = '';
  ok = false;

  ngOnInit(): void {
    this.auth.preloadPublicKey();
    this.token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!this.token) {
      this.notify.warning('Enlace inválido', 'Solicita un nuevo enlace desde ingresar.');
    }
  }

  submit(): void {
    if (this.password !== this.password2) {
      this.notify.warning('Contraseñas', 'Las contraseñas no coinciden');
      return;
    }
    if (!this.token) return;
    this.notify.loadingTheatrical('Actualizando', 'login');
    this.auth.resetPassword(this.token, this.password).subscribe({
      next: () => {
        this.notify.hide();
        this.ok = true;
        this.notify.success('Listo', 'Contraseña actualizada');
        setTimeout(() => this.router.navigate(['/ingresar']), 2000);
      },
      error: (err) => {
        this.notify.hide();
        this.notify.showHttpError(parseHttpError(err, 'reset-password'));
      },
    });
  }
}
