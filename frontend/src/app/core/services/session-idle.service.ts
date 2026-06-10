import { Injectable, inject } from '@angular/core';
import { AuthService } from './auth.service';
import { NotificationService } from './notification.service';

const IDLE_MS = 5 * 60 * 1000;

@Injectable({ providedIn: 'root' })
export class SessionIdleService {
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private timer: ReturnType<typeof setTimeout> | null = null;
  private started = false;

  start(): void {
    if (this.started || typeof window === 'undefined') return;
    this.started = true;
    const reset = () => this.arm();
    ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'].forEach((ev) => {
      window.addEventListener(ev, reset, { passive: true });
    });
    this.arm();
  }

  private arm(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.onIdle(), IDLE_MS);
  }

  private onIdle(): void {
    if (!this.auth.isLoggedIn()) {
      this.arm();
      return;
    }
    this.notify.warning('Sesión cerrada', 'Por inactividad (5 min). Vuelve a ingresar.');
    this.auth.logout();
  }
}
