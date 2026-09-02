import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { HttpBackend, HttpClient, HttpErrorResponse } from '@angular/common/http';
import { catchError, firstValueFrom, from, switchMap, tap, throwError, timeout, TimeoutError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApiService } from './api.service';
import { encryptPasswordForTransport } from '../utils/password-crypto.util';

export interface TavaUser {
  id: string;
  email: string;
  full_name: string;
  role: 'general' | 'admin' | 'organizer' | 'validator' | 'seller';
  is_platform_admin?: boolean;
}

interface AuthResponse {
  user: TavaUser;
  tokens: { access_token: string; refresh_token: string; token_type: string };
}

const LOGIN_TIMEOUT_MS = 18000;

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly httpBackend = inject(HttpBackend);
  private publicKeyPem: string | null = null;
  private publicKeyInflight: Promise<string> | null = null;
  private refreshInflight: Promise<string | null> | null = null;

  private readonly _user = signal<TavaUser | null>(this.loadUser());
  readonly user = this._user.asReadonly();
  readonly isLoggedIn = computed(() => !!this._user());
  readonly isPlatformAdmin = computed(() => !!this._user()?.is_platform_admin);
  readonly isOrganizer = computed(() => this._user()?.role === 'organizer');
  readonly canManageEvents = computed(() => this.isPlatformAdmin() || this.isOrganizer());
  readonly isAdmin = computed(() => this.isPlatformAdmin());
  readonly isValidator = computed(() => {
    const role = this._user()?.role ?? '';
    return role === 'validator' || this.isPlatformAdmin();
  });
  readonly isSeller = computed(() => {
    const role = this._user()?.role ?? '';
    return role === 'seller' || this.isPlatformAdmin();
  });

  constructor() {
    this.recoverStoredSession();
  }

  preloadPublicKey(): void {
    void this.getPublicKeyPem().catch(() => undefined);
  }

  login(email: string, password: string, captchaToken?: string) {
    return from(this.getPublicKeyPem()).pipe(
      switchMap((public_key_pem) =>
        from(encryptPasswordForTransport(public_key_pem, password)).pipe(
          switchMap((password_encrypted) =>
            this.api.post<AuthResponse>('/auth/login', {
              email,
              password_encrypted,
              captcha_token: captchaToken,
            })
          )
        )
      ),
      timeout(LOGIN_TIMEOUT_MS),
      tap((res) => this.persist(res)),
      catchError((err) => {
        if (err instanceof TimeoutError) {
          this.publicKeyInflight = null;
          return throwError(
            () =>
              new HttpErrorResponse({
                error: {
                  detail: 'El servidor se demoró mucho, vuelve a intentarlo.',
                  code: 'LOGIN_TIMEOUT',
                },
                status: 0,
                statusText: 'Timeout',
                url: `${environment.apiUrl}/auth/login`,
              })
          );
        }
        return throwError(() => err);
      })
    );
  }

  register(data: {
    email: string;
    password: string;
    full_name: string;
    phone: string;
    accept_privacy_policy: boolean;
    accept_marketing?: boolean;
    captcha_token?: string;
  }) {
    return from(this.getPublicKeyPem()).pipe(
      switchMap((public_key_pem) =>
        from(encryptPasswordForTransport(public_key_pem, data.password)).pipe(
          switchMap((password_encrypted) =>
            this.api.post<{
              message: string;
              user: TavaUser;
              email_sent: boolean;
            }>('/auth/register', {
              email: data.email,
              full_name: data.full_name,
              phone: data.phone,
              accept_privacy_policy: data.accept_privacy_policy,
              accept_marketing: data.accept_marketing ?? false,
              password_encrypted,
              captcha_token: data.captcha_token,
            })
          )
        )
      )
    );
  }

  resendVerification(email: string) {
    return this.api.post<{ message: string; email_sent: boolean; success: boolean }>(
      `/auth/resend-verification?email=${encodeURIComponent(email)}`,
      {}
    );
  }

  verifyEmail(token: string) {
    return this.api.get<{ message: string; success: boolean }>(`/auth/verify-email?token=${encodeURIComponent(token)}`);
  }

  forgotPassword(email: string, captchaToken: string) {
    const normalized = email.trim().toLowerCase();
    return this.api.post<{ message: string; success: boolean; email_sent?: boolean }>(
      '/auth/forgot-password',
      { email: normalized, captcha_token: captchaToken }
    );
  }

  resetPassword(token: string, password: string, captchaToken: string) {
    return from(this.getPublicKeyPem()).pipe(
      switchMap((public_key_pem) =>
        from(encryptPasswordForTransport(public_key_pem, password)).pipe(
          switchMap((password_encrypted) =>
            this.api.post<{ message: string; success: boolean }>('/auth/reset-password', {
              token,
              password_encrypted,
              captcha_token: captchaToken,
            })
          )
        )
      )
    );
  }

  logout(): void {
    this.clearStoredSession();
    this._user.set(null);
    this.router.navigate(['/']);
  }

  getAccessToken(): string | null {
    return localStorage.getItem('tava_access');
  }

  getRefreshToken(): string | null {
    return localStorage.getItem('tava_refresh');
  }

  /** Renueva el access token si hay refresh guardado (p. ej. al volver a la app). */
  tryRefreshSession(): Promise<boolean> {
    return this.refreshAccessToken().then((token) => !!token);
  }

  /** Una única renovación compartida para arranque e interceptor. */
  refreshAccessToken(): Promise<string | null> {
    if (this.refreshInflight) return this.refreshInflight;
    const refresh = this.getRefreshToken();
    if (!refresh) return Promise.resolve(null);
    const raw = new HttpClient(this.httpBackend);
    const url = `${environment.apiUrl}/auth/refresh?refresh_token=${encodeURIComponent(refresh)}`;
    this.refreshInflight = firstValueFrom(
      raw.post<AuthResponse['tokens']>(url, {}).pipe(timeout(12000))
    )
      .then((tokens) => {
        localStorage.setItem('tava_access', tokens.access_token);
        localStorage.setItem('tava_refresh', tokens.refresh_token);
        return tokens.access_token;
      })
      .catch(() => null)
      .finally(() => {
        this.refreshInflight = null;
      });
    return this.refreshInflight;
  }

  private persist(res: AuthResponse): void {
    localStorage.setItem('tava_access', res.tokens.access_token);
    localStorage.setItem('tava_refresh', res.tokens.refresh_token);
    localStorage.setItem('tava_user', JSON.stringify(res.user));
    this._user.set(res.user);
  }

  private recoverStoredSession(): void {
    const user = this._user();
    if (!user) return;
    const access = this.getAccessToken();
    const refresh = this.getRefreshToken();
    if (!access || !refresh) {
      this.clearStoredSession();
      this._user.set(null);
      return;
    }
    if (!this.isJwtExpired(access)) return;
    void this.tryRefreshSession().then((ok) => {
      if (!ok) {
        this.clearStoredSession();
        this._user.set(null);
      }
    });
  }

  private clearStoredSession(): void {
    localStorage.removeItem('tava_access');
    localStorage.removeItem('tava_refresh');
    localStorage.removeItem('tava_user');
  }

  private isJwtExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))) as {
        exp?: number;
      };
      if (!payload.exp) return true;
      return payload.exp * 1000 <= Date.now() + 15000;
    } catch {
      return true;
    }
  }

  private getPublicKeyPem(): Promise<string> {
    if (this.publicKeyPem) return Promise.resolve(this.publicKeyPem);
    if (this.publicKeyInflight) return this.publicKeyInflight;
    this.publicKeyInflight = firstValueFrom(this.api.get<{ public_key_pem: string }>('/auth/public-key'))
      .then(({ public_key_pem }) => {
        this.publicKeyPem = public_key_pem;
        return public_key_pem;
      })
      .finally(() => {
        this.publicKeyInflight = null;
      });
    return this.publicKeyInflight;
  }

  private loadUser(): TavaUser | null {
    const token = localStorage.getItem('tava_access');
    const refresh = localStorage.getItem('tava_refresh');
    if (!token || !refresh) {
      this.clearStoredSession();
      return null;
    }
    const raw = localStorage.getItem('tava_user');
    if (!raw) return null;
    try {
      return JSON.parse(raw) as TavaUser;
    } catch {
      return null;
    }
  }
}
