import { AfterViewInit, Component, inject, OnDestroy, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Html5Qrcode } from 'html5-qrcode';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEvent } from '../../core/models/event.model';

interface ScanResponse {
  result: string;
  message: string;
  holder_name?: string | null;
  event_name?: string | null;
  event_id?: string | null;
  ingresados?: number | null;
  boletas_vendidas?: number | null;
  pendientes_ingreso?: number | null;
}

interface Attendee {
  ticket_id: string;
  holder_name: string | null;
  ticket_code?: string | null;
  is_used: boolean;
  used_at: string | null;
}

interface AttendeesResponse {
  event_id: string;
  event_name: string;
  ingresados: number;
  boletas_vendidas: number;
  pendientes_ingreso: number;
  attendees: Attendee[];
}

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

  readonly events = signal<TavaEvent[]>([]);
  readonly attendees = signal<Attendee[]>([]);
  readonly stats = signal({
    ingresados: 0,
    boletas_vendidas: 0,
    pendientes_ingreso: 0,
    event_name: '',
  });

  selectedEventId = '';
  qrToken = '';
  lastResult = '';
  lastHolderName = '';
  lastStatus: 'ok' | 'warn' | 'error' | '' = '';
  cameraError = '';
  cameraActive = false;

  ngAfterViewInit(): void {
    this.loadEvents();
    void this.startCamera();
  }

  ngOnDestroy(): void {
    void this.stopCamera();
  }

  loadEvents(): void {
    this.api.get<TavaEvent[]>('/events/assigned/mine', { staff_role: 'validator' }).subscribe({
      next: (evs) => {
        this.events.set(evs);
        if (evs.length && !this.selectedEventId) {
          this.selectedEventId = evs[0].id;
          this.loadAttendees();
        }
      },
    });
  }

  onEventChange(): void {
    this.loadAttendees();
  }

  loadAttendees(): void {
    if (!this.selectedEventId) {
      this.attendees.set([]);
      return;
    }
    this.api.get<AttendeesResponse>(`/validation/attendees/${this.selectedEventId}`).subscribe({
      next: (data) => {
        this.attendees.set(data.attendees);
        this.stats.set({
          ingresados: data.ingresados,
          boletas_vendidas: data.boletas_vendidas,
          pendientes_ingreso: data.pendientes_ingreso,
          event_name: data.event_name,
        });
      },
      error: () => this.attendees.set([]),
    });
  }

  async startCamera(): Promise<void> {
    if (this.scanning) return;
    this.cameraError = '';
    try {
      this.scanner = new Html5Qrcode('qr-reader');
      await this.scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 280, height: 280 }, aspectRatio: 1 },
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
    this.api.post<ScanResponse>('/validation/scan', { qr_token: token }).subscribe({
      next: (res) => {
        this.lastResult = res.message;
        this.lastHolderName = res.holder_name ?? '';
        this.lastStatus = res.result === 'acceso_autorizado' ? 'ok' : 'warn';

        if (res.event_id) {
          this.selectedEventId = res.event_id;
        }
        if (res.ingresados != null) {
          this.stats.set({
            ingresados: res.ingresados,
            boletas_vendidas: res.boletas_vendidas ?? 0,
            pendientes_ingreso: res.pendientes_ingreso ?? 0,
            event_name: res.event_name ?? this.stats().event_name,
          });
        }

        if (res.result === 'acceso_autorizado') {
          this.notify.success('Acceso', res.holder_name ? `${res.holder_name} — ingreso autorizado` : res.message);
        } else {
          this.notify.warning('Validación', res.message);
        }

        this.qrToken = '';
        this.loadAttendees();
      },
      error: (err) => {
        this.lastStatus = 'error';
        this.lastResult = err?.error?.detail ?? 'Fallo de validación';
        this.notify.error('Error', this.lastResult);
      },
    });
  }
}
