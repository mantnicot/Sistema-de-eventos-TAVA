import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError, from } from 'rxjs';
import { AuthService } from '../services/auth.service';

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

  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status !== 401 || shouldSkipRefresh(req.url) || !auth.getRefreshToken()) {
        return throwError(() => err);
      }

      return from(auth.refreshAccessToken()).pipe(
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
