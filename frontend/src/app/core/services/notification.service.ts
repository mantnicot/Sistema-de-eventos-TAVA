import { Injectable, signal } from '@angular/core';
import { ParsedHttpError } from '../utils/http-error.util';
import { randomTheatricalMessage } from '../utils/theatrical-messages.util';

export type NotifyType = 'success' | 'error' | 'confirm' | 'warning' | 'loading' | 'celebration';

export interface NotifyState {
  visible: boolean;
  type: NotifyType;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm?: () => void;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  readonly state = signal<NotifyState | null>(null);
  private autoHideTimer: ReturnType<typeof setTimeout> | null = null;

  success(title: string, message: string): void {
    this.show({ visible: true, type: 'success', title, message });
    this.scheduleHide(4200);
  }

  error(title: string, message: string): void {
    this.show({ visible: true, type: 'error', title, message });
    this.scheduleHide(6500);
  }

  /** Muestra popup según si el fallo es del usuario, del sistema o de red. */
  showHttpError(parsed: ParsedHttpError): void {
    const type = parsed.kind === 'user' ? 'warning' : 'error';
    this.show({ visible: true, type, title: parsed.title, message: parsed.message });
    this.scheduleHide(parsed.kind === 'user' ? 5200 : 7000);
  }

  warning(title: string, message: string): void {
    this.show({ visible: true, type: 'warning', title, message });
    this.scheduleHide(5500);
  }

  loading(title: string, message = 'Cargando...'): void {
    this.show({ visible: true, type: 'loading', title, message });
  }

  /** Mensaje de espera con humor teatral TAVA. */
  loadingTheatrical(title: string, context = 'general'): void {
    this.loading(title, randomTheatricalMessage(context));
  }

  confirm(title: string, message: string, onConfirm: () => void, confirmLabel = 'Confirmar'): void {
    this.show({ visible: true, type: 'confirm', title, message, confirmLabel, onConfirm });
  }

  /** Mensaje grande de agradecimiento tras compra exitosa. */
  celebration(title: string, message: string): void {
    this.show({ visible: true, type: 'celebration', title, message });
  }

  hide(): void {
    this.clearAutoHide();
    this.state.set(null);
  }

  private show(s: NotifyState): void {
    this.clearAutoHide();
    this.state.set(s);
  }

  private scheduleHide(ms: number): void {
    this.clearAutoHide();
    this.autoHideTimer = setTimeout(() => this.hide(), ms);
  }

  private clearAutoHide(): void {
    if (this.autoHideTimer) {
      clearTimeout(this.autoHideTimer);
      this.autoHideTimer = null;
    }
  }
}
