import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-validation',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './validation.component.html',
  styleUrl: './validation.component.scss',
})
export class ValidationComponent {
  private readonly api = inject(ApiService);
  private readonly notify = inject(NotificationService);
  qrToken = '';
  lastResult = '';

  scan(): void {
    if (!this.qrToken.trim()) return;
    this.notify.loading('Validando', 'Verificando boleta...');
    this.api.post<{ result: string; message: string }>('/validation/scan', { qr_token: this.qrToken }).subscribe({
      next: (res) => {
        this.notify.hide();
        this.lastResult = res.message;
        if (res.result === 'acceso_autorizado') {
          this.notify.success('Acceso', res.message);
        } else {
          this.notify.warning('Validación', res.message);
        }
        this.qrToken = '';
      },
      error: (err) => {
        this.notify.hide();
        this.notify.error('Error', err?.error?.detail ?? 'Fallo de validación');
      },
    });
  }
}
