import { AfterViewInit, Component, inject, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Html5Qrcode } from 'html5-qrcode';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-validation',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './validation.component.html',
  styleUrl: './validation.component.scss',
})
export class ValidationComponent implements AfterViewInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly notify = inject(NotificationService);
  private scanner: Html5Qrcode | null = null;
  private scanning = false;
  private lastScanAt = 0;

  qrToken = '';
  lastResult = '';
  cameraError = '';
  cameraActive = false;

  ngAfterViewInit(): void {
    void this.startCamera();
  }

  ngOnDestroy(): void {
    void this.stopCamera();
  }

  async startCamera(): Promise<void> {
    if (this.scanning) return;
    this.cameraError = '';
    try {
      this.scanner = new Html5Qrcode('qr-reader');
      await this.scanner.start(
        { facingMode: 'environment' },
        { fps: 8, qrbox: { width: 240, height: 240 }, aspectRatio: 1 },
        (decoded) => this.onQrDecoded(decoded),
        () => {}
      );
      this.scanning = true;
      this.cameraActive = true;
    } catch {
      this.cameraError = 'No se pudo abrir la cámara. Usa el campo manual o revisa los permisos.';
      this.cameraActive = false;
    }
  }

  async stopCamera(): Promise<void> {
    if (!this.scanner || !this.scanning) return;
    try {
      await this.scanner.stop();
      await this.scanner.clear();
    } catch {
      /* ignore */
    }
    this.scanning = false;
    this.cameraActive = false;
    this.scanner = null;
  }

  async toggleCamera(): Promise<void> {
    if (this.cameraActive) {
      await this.stopCamera();
    } else {
      await this.startCamera();
    }
  }

  private onQrDecoded(text: string): void {
    const now = Date.now();
    if (now - this.lastScanAt < 2500) return;
    this.lastScanAt = now;
    this.qrToken = this.extractToken(text);
    this.scan();
  }

  private extractToken(raw: string): string {
    const trimmed = raw.trim();
    if (!trimmed) return '';
    try {
      const url = new URL(trimmed);
      const token = url.searchParams.get('token') ?? url.searchParams.get('qr');
      if (token) return token;
      const parts = url.pathname.split('/').filter(Boolean);
      return parts[parts.length - 1] ?? trimmed;
    } catch {
      return trimmed;
    }
  }

  scan(): void {
    const token = this.qrToken.trim();
    if (!token) return;
    this.notify.loadingTheatrical('Validando', 'validation');
    this.api.post<{ result: string; message: string }>('/validation/scan', { qr_token: token }).subscribe({
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
