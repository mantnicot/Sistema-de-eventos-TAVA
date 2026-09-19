import { AfterViewInit, Component, computed, inject, OnDestroy, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Html5Qrcode } from 'html5-qrcode';
import { ApiService } from '../../core/services/api.service';
import { TavaEvent } from '../../core/models/event.model';
import { matchesSearch } from '../../core/utils/list-search.util';
import { TavaListSearchComponent } from '../../shared/components/tava-list-search/tava-list-search.component';

interface ScanResponse {
  result: string;
  message: string;
  holder_name?: string | null;
  ticket_code?: string | null;
  event_name?: string | null;
  ticket_event_name?: string | null;
  event_id?: string | null;
  ticket_id?: string | null;
  ingresados?: number | null;
  boletas_vendidas?: number | null;
  pendientes_ingreso?: number | null;
}

interface Attendee {
  ticket_id: string;
  holder_name: string | null;
  recipient_name?: string | null;
  recipient_email?: string | null;
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

type ResultTone = 'ok' | 'warn' | 'deny' | '';

@Component({
  selector: 'app-validation',
  standalone: true,
  imports: [FormsModule, TavaListSearchComponent],
  templateUrl: './validation.component.html',
  styleUrl: './validation.component.scss',
})
export class ValidationComponent implements AfterViewInit, OnDestroy {
  private readonly api = inject(ApiService);
  private scanner: Html5Qrcode | null = null;
  private scanning = false;
  private lastScanAt = 0;
  private lastToken = '';
  private clearResultTimer: ReturnType<typeof setTimeout> | null = null;
  private audioCtx: AudioContext | null = null;
  private busy = false;

  readonly events = signal<TavaEvent[]>([]);
  readonly attendees = signal<Attendee[]>([]);
  readonly stats = signal({
    ingresados: 0,
    boletas_vendidas: 0,
    pendientes_ingreso: 0,
    event_name: '',
  });
  readonly showAttendees = signal(false);
  readonly scanningBusy = signal(false);

  readonly selectedEventId = signal('');
  qrToken = '';
  lastHeadline = '';
  lastMessage = '';
  lastHolderName = '';
  lastTicketCode = '';
  lastExtra = '';
  lastTone: ResultTone = '';
  cameraError = '';
  cameraActive = false;
  readonly attendeeQuery = signal('');

  readonly filteredAttendees = computed(() =>
    this.attendees().filter((a) =>
      matchesSearch(
        this.attendeeQuery(),
        a.holder_name,
        a.recipient_name,
        a.recipient_email,
        a.ticket_code,
        a.is_used ? 'ingreso ingresó' : 'pendiente'
      )
    )
  );

  readonly selectedEventLabel = computed(() => {
    const id = this.selectedEventId();
    const ev = this.events().find((e) => e.id === id);
    return ev ? `${ev.name} · ${ev.event_date}` : this.stats().event_name || 'Selecciona un evento';
  });

  ngAfterViewInit(): void {
    this.loadEvents();
  }

  ngOnDestroy(): void {
    if (this.clearResultTimer) clearTimeout(this.clearResultTimer);
    void this.stopCamera();
    void this.audioCtx?.close();
  }

  loadEvents(): void {
    this.api.get<TavaEvent[]>('/events/assigned/mine', { staff_role: 'validator' }).subscribe({
      next: (evs) => {
        this.events.set(evs);
        if (evs.length && !this.selectedEventId()) {
          this.selectedEventId.set(evs[0].id);
          this.loadAttendees();
          void this.startCamera();
        }
      },
    });
  }

  onEventChange(id: string): void {
    this.selectedEventId.set(id);
    this.clearResult();
    this.loadAttendees();
    if (id && !this.cameraActive) {
      void this.startCamera();
    }
  }

  loadAttendees(): void {
    const eventId = this.selectedEventId();
    if (!eventId) {
      this.attendees.set([]);
      this.attendeeQuery.set('');
      this.stats.set({
        ingresados: 0,
        boletas_vendidas: 0,
        pendientes_ingreso: 0,
        event_name: '',
      });
      return;
    }
    this.api.get<AttendeesResponse>(`/validation/attendees/${eventId}`).subscribe({
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

  toggleAttendees(): void {
    const next = !this.showAttendees();
    this.showAttendees.set(next);
    if (next) this.loadAttendees();
  }

  async startCamera(): Promise<void> {
    if (this.scanning || !this.selectedEventId()) return;
    this.cameraError = '';
    try {
      this.scanner = new Html5Qrcode('qr-reader');
      await this.scanner.start(
        { facingMode: 'environment' },
        { fps: 18, qrbox: { width: 260, height: 260 }, aspectRatio: 1 },
        (decoded) => this.onQrDecoded(decoded),
        () => {}
      );
      this.scanning = true;
      this.cameraActive = true;
    } catch {
      this.cameraError = 'No se pudo abrir la cámara. Usa el código manual o revisa los permisos.';
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
    if (this.busy || this.scanningBusy()) return;
    const token = this.extractToken(text);
    if (!token) return;
    const now = Date.now();
    const cooldown = this.lastTone === 'ok' ? 1400 : 900;
    if (token === this.lastToken && now - this.lastScanAt < cooldown) return;
    if (now - this.lastScanAt < 700) return;
    this.lastScanAt = now;
    this.lastToken = token;
    this.qrToken = token;
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
    if (!token || this.busy) return;
    const eventId = this.selectedEventId();
    if (!eventId) {
      this.showResult({
        tone: 'deny',
        headline: 'Elige el evento',
        message: 'Selecciona la función antes de validar.',
        holder: '',
        code: '',
        extra: '',
      });
      return;
    }

    this.busy = true;
    this.scanningBusy.set(true);
    this.api
      .post<ScanResponse>('/validation/scan', {
        qr_token: token,
        event_id: eventId,
      })
      .subscribe({
        next: (res) => {
          this.busy = false;
          this.scanningBusy.set(false);
          this.applyScanResult(res);
          this.qrToken = '';
        },
        error: (err) => {
          this.busy = false;
          this.scanningBusy.set(false);
          this.showResult({
            tone: 'deny',
            headline: 'Error',
            message: err?.error?.detail ?? 'No se pudo validar',
            holder: '',
            code: '',
            extra: '',
          });
          this.playFeedback(false);
        },
      });
  }

  private applyScanResult(res: ScanResponse): void {
    if (res.ingresados != null) {
      this.stats.set({
        ingresados: res.ingresados,
        boletas_vendidas: res.boletas_vendidas ?? this.stats().boletas_vendidas,
        pendientes_ingreso: res.pendientes_ingreso ?? this.stats().pendientes_ingreso,
        event_name: res.event_name ?? this.stats().event_name,
      });
    }

    if (res.result === 'acceso_autorizado' && res.ticket_id) {
      const tid = String(res.ticket_id);
      this.attendees.update((list) =>
        list.map((a) =>
          String(a.ticket_id) === tid
            ? { ...a, is_used: true, used_at: new Date().toISOString() }
            : a
        )
      );
    }
    const holder = res.holder_name?.trim() || '';
    const code = res.ticket_code ? `#${res.ticket_code}` : '';

    switch (res.result) {
      case 'acceso_autorizado':
        this.showResult({
          tone: 'ok',
          headline: 'PUEDE ENTRAR',
          message: 'Boleta válida · permiso autorizado',
          holder,
          code,
          extra: '',
        });
        this.playFeedback(true);
        break;
      case 'boleta_ya_utilizada':
        this.showResult({
          tone: 'warn',
          headline: 'YA INGRESÓ',
          message: 'Esta boleta ya fue usada',
          holder,
          code,
          extra: '',
        });
        this.playFeedback(false);
        break;
      case 'boleta_otro_evento':
        this.showResult({
          tone: 'deny',
          headline: 'EVENTO INCORRECTO',
          message: 'Esta boleta no es de esta función',
          holder,
          code,
          extra: res.ticket_event_name ? `Pertenece a: ${res.ticket_event_name}` : '',
        });
        this.playFeedback(false);
        break;
      case 'boleta_cancelada':
        this.showResult({
          tone: 'deny',
          headline: 'NO PUEDE ENTRAR',
          message: 'La boleta está cancelada',
          holder,
          code,
          extra: '',
        });
        this.playFeedback(false);
        break;
      case 'evento_no_habilitado':
        this.showResult({
          tone: 'deny',
          headline: 'INGRESO BLOQUEADO',
          message: 'El admin debe liquidar el evento en Revisión',
          holder,
          code,
          extra: '',
        });
        this.playFeedback(false);
        break;
      case 'no_autorizado':
        this.showResult({
          tone: 'deny',
          headline: 'SIN PERMISO',
          message: 'Tu usuario no puede validar este evento',
          holder,
          code,
          extra: '',
        });
        this.playFeedback(false);
        break;
      default:
        this.showResult({
          tone: 'deny',
          headline: 'NO VÁLIDA',
          message: 'No reconocimos esta boleta',
          holder,
          code,
          extra: '',
        });
        this.playFeedback(false);
    }
  }

  private showResult(opts: {
    tone: ResultTone;
    headline: string;
    message: string;
    holder: string;
    code: string;
    extra: string;
  }): void {
    this.lastTone = opts.tone;
    this.lastHeadline = opts.headline;
    this.lastMessage = opts.message;
    this.lastHolderName = opts.holder;
    this.lastTicketCode = opts.code;
    this.lastExtra = opts.extra;
    if (this.clearResultTimer) clearTimeout(this.clearResultTimer);
    this.clearResultTimer = setTimeout(() => this.clearResult(), opts.tone === 'ok' ? 2200 : 2800);
  }

  clearResult(): void {
    this.lastTone = '';
    this.lastHeadline = '';
    this.lastMessage = '';
    this.lastHolderName = '';
    this.lastTicketCode = '';
    this.lastExtra = '';
  }

  private playFeedback(ok: boolean): void {
    try {
      if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
        navigator.vibrate(ok ? [40] : [80, 40, 80]);
      }
    } catch {
      /* ignore */
    }
    try {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      this.audioCtx ??= new Ctx();
      const ctx = this.audioCtx;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.value = ok ? 880 : 220;
      gain.gain.value = 0.04;
      osc.start();
      osc.stop(ctx.currentTime + (ok ? 0.12 : 0.22));
    } catch {
      /* ignore */
    }
  }
}
