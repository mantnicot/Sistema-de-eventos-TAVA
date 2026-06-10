import { HttpBackend, HttpClient, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError, from } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

let refreshPromise: Promise<string | null> | null = null;

function shouldSkipRefresh(url: string): boolean {
  return (
    url.includes('/auth/login') ||
    url.includes('/auth/register') ||
    url.includes('/auth/refresh') ||
    url.includes('/auth/public-key')
  );
}

export const tokenRefreshInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const httpBackend = inject(HttpBackend);

  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status !== 401 || shouldSkipRefresh(req.url) || !auth.getRefreshToken()) {
        return throwError(() => err);
      }

      if (!refreshPromise) {
        const raw = new HttpClient(httpBackend);
        const refresh = auth.getRefreshToken()!;
        const url = `${environment.apiUrl}/auth/refresh?refresh_token=${encodeURIComponent(refresh)}`;
        refreshPromise = new Promise<string | null>((resolve) => {
          raw.post<TokenResponse>(url, {}).subscribe({
            next: (tokens) => {
              localStorage.setItem('tava_access', tokens.access_token);
              localStorage.setItem('tava_refresh', tokens.refresh_token);
              resolve(tokens.access_token);
            },
            error: () => resolve(null),
          });
        }).finally(() => {
          refreshPromise = null;
        });
      }

      return from(refreshPromise).pipe(
        switchMap((token) => {
          if (!token) {
            auth.logout();
            return throwError(() => err);
          }
          const retry = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
          return next(retry);
        })
      );
    })
  );
};
