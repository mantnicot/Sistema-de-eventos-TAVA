import { HttpContextToken, HttpErrorResponse, HttpEvent, HttpInterceptorFn } from '@angular/common/http';
import { Observable, catchError, switchMap, throwError, timer } from 'rxjs';

const RETRYABLE = new Set([0, 502, 503, 504]);
const DELAYS_MS = [600, 1800, 4000];
const MAX_RETRIES = 3;

/** No reintentar compras/ventas para evitar duplicados accidentales. */
export const SKIP_RETRY = new HttpContextToken<boolean>(() => false);

export const retryInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.context.get(SKIP_RETRY)) {
    return next(req);
  }
  const isSafeRetry =
    req.method === 'GET' ||
    req.method === 'HEAD' ||
    req.url.includes('/ping') ||
    req.url.includes('/settings/appearance') ||
    req.url.includes('/events');

  const attempt = (retryIndex: number): Observable<HttpEvent<unknown>> =>
    next(req).pipe(
      catchError((err: HttpErrorResponse): Observable<HttpEvent<unknown>> => {
        const status = err.status ?? 0;
        if (!RETRYABLE.has(status) || retryIndex >= MAX_RETRIES) {
          return throwError(() => err);
        }
        if (!isSafeRetry && status !== 0) {
          return throwError(() => err);
        }
        const delay = DELAYS_MS[retryIndex] ?? 8000;
        return timer(delay).pipe(switchMap(() => attempt(retryIndex + 1)));
      })
    );

  return attempt(0);
};
