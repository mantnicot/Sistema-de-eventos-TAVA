import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { ApiService } from './api.service';

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

  login(email: string, password: string, captchaToken?: string) {
    return this.api.post<AuthResponse>('/auth/login', { email, password, captcha_token: captchaToken }).pipe(
      tap((res) => this.persist(res))
    );
  }

  register(data: { email: string; password: string; full_name: string; captcha_token?: string }) {
    return this.api.post<AuthResponse>('/auth/register', data).pipe(tap((res) => this.persist(res)));
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
