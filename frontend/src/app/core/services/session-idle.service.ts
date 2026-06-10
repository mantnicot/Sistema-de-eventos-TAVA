import { Injectable, inject } from '@angular/core';
import { AuthService } from './auth.service';
import { NotificationService } from './notification.service';

/** Tiempo de inactividad antes de cerrar sesión (solo con pestaña visible). */
const IDLE_MS = 20 * 60 * 1000;

@Injectable({ providedIn: 'root' })
export class SessionIdleService {
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private timer: ReturnType<typeof setTimeout> | null = null;
  private started = false;
  private tabHidden = false;

  start(): void {
    if (this.started || typeof window === 'undefined') return;
    this.started = true;
    const reset = () => {
      if (!this.tabHidden) this.arm();
    };
    ['click', 'keydown', 'mousemove', 'scroll', 'touchstart'].forEach((ev) => {
      window.addEventListener(ev, reset, { passive: true });
    });
    document.addEventListener('visibilitychange', () => this.onVisibilityChange());
    this.arm();
  }

  private onVisibilityChange(): void {
    this.tabHidden = document.hidden;
    if (this.tabHidden) {
      if (this.timer) clearTimeout(this.timer);
      return;
    }
    this.arm();
    if (this.auth.isLoggedIn()) {
      void this.auth.tryRefreshSession();
    }
  }

  private arm(): void {
    if (this.tabHidden) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.onIdle(), IDLE_MS);
  }

  private onIdle(): void {
    if (!this.auth.isLoggedIn() || this.tabHidden) {
      this.arm();
      return;
    }
    this.notify.warning('Sesión cerrada', 'Por inactividad. Vuelve a ingresar.');
    this.auth.logout();
  }
}
