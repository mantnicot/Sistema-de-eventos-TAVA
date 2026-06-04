import { Injectable, signal } from '@angular/core';
import { ParsedHttpError } from '../utils/http-error.util';
import { randomTheatricalMessage } from '../utils/theatrical-messages.util';

export type NotifyType = 'success' | 'error' | 'confirm' | 'warning' | 'loading';

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

  success(title: string, message: string): void {
    this.show({ visible: true, type: 'success', title, message });
    setTimeout(() => this.hide(), 3500);
  }

  error(title: string, message: string): void {
    this.show({ visible: true, type: 'error', title, message });
    setTimeout(() => this.hide(), 5000);
  }

  /** Muestra popup según si el fallo es del usuario, del sistema o de red. */
  showHttpError(parsed: ParsedHttpError): void {
    const type = parsed.kind === 'user' ? 'warning' : 'error';
    this.show({ visible: true, type, title: parsed.title, message: parsed.message });
    setTimeout(() => this.hide(), parsed.kind === 'user' ? 4500 : 6000);
  }

  warning(title: string, message: string): void {
    this.show({ visible: true, type: 'warning', title, message });
    setTimeout(() => this.hide(), 4500);
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

  hide(): void {
    this.state.set(null);
  }

  private show(s: NotifyState): void {
    this.state.set(s);
  }
}
