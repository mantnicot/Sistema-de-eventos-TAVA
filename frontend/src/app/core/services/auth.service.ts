import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { from, switchMap, tap } from 'rxjs';
import { ApiService } from './api.service';
import { encryptPasswordForTransport } from '../utils/password-crypto.util';

export interface TavaUser {
  id: string;
  email: string;
  full_name: string;
  role: 'general' | 'admin' | 'validator' | 'seller';
}

interface AuthResponse {
  user: TavaUser;
  tokens: { access_token: string; refresh_token: string; token_type: string };
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  private readonly _user = signal<TavaUser | null>(this.loadUser());
  readonly user = this._user.asReadonly();
  readonly isLoggedIn = computed(() => !!this._user());
  readonly isAdmin = computed(() => this._user()?.role === 'admin');
  readonly isValidator = computed(() => ['validator', 'admin'].includes(this._user()?.role ?? ''));
  readonly isSeller = computed(() => ['seller', 'admin'].includes(this._user()?.role ?? ''));

  login(email: string, password: string, captchaToken?: string) {
    return this.api.get<{ public_key_pem: string }>('/auth/public-key').pipe(
      switchMap(({ public_key_pem }) =>
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
      tap((res) => this.persist(res))
    );
  }

  register(data: { email: string; password: string; full_name: string; captcha_token?: string }) {
    return this.api.get<{ public_key_pem: string }>('/auth/public-key').pipe(
      switchMap(({ public_key_pem }) =>
        from(encryptPasswordForTransport(public_key_pem, data.password)).pipe(
          switchMap((password_encrypted) =>
            this.api.post<{
              message: string;
              user: TavaUser;
              dev_verification_url?: string;
            }>('/auth/register', {
              email: data.email,
              full_name: data.full_name,
              password_encrypted,
              captcha_token: data.captcha_token,
            })
          )
        )
      )
    );
  }

  resendVerification(email: string) {
    return this.api.post<{ message: string }>(`/auth/resend-verification?email=${encodeURIComponent(email)}`, {});
  }

  verifyEmail(token: string) {
    return this.api.get<{ message: string; success: boolean }>(`/auth/verify-email?token=${encodeURIComponent(token)}`);
  }

  logout(): void {
    localStorage.removeItem('tava_access');
    localStorage.removeItem('tava_refresh');
    localStorage.removeItem('tava_user');
    this._user.set(null);
    this.router.navigate(['/']);
  }

  getAccessToken(): string | null {
    return localStorage.getItem('tava_access');
  }

  private persist(res: AuthResponse): void {
    localStorage.setItem('tava_access', res.tokens.access_token);
    localStorage.setItem('tava_refresh', res.tokens.refresh_token);
    localStorage.setItem('tava_user', JSON.stringify(res.user));
    this._user.set(res.user);
  }

  private loadUser(): TavaUser | null {
    const raw = localStorage.getItem('tava_user');
    if (!raw) return null;
    try {
      return JSON.parse(raw) as TavaUser;
    } catch {
      return null;
    }
  }
}
