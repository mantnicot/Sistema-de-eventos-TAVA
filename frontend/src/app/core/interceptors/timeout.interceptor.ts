import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError, timeout, TimeoutError } from 'rxjs';

/** Evita peticiones colgadas indefinidamente (Render cold start). */
const READ_TIMEOUT_MS = 65000;
const WRITE_TIMEOUT_MS = 25000;
const TICKET_WRITE_TIMEOUT_MS = 90000;

const LONG_TICKET_WRITE_PATHS = [
  '/tickets/sell',
  '/tickets/admin/issue-claim',
  '/tickets/purchase',
  '/payments/wompi/confirm/',
];

export const timeoutInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url.includes('/uploads/') || req.responseType === 'blob') {
    return next(req);
  }
  const isLongTicketWrite =
    req.method !== 'GET' &&
    req.method !== 'HEAD' &&
    LONG_TICKET_WRITE_PATHS.some((path) => req.url.includes(path));
  const timeoutMs =
    req.method === 'GET' || req.method === 'HEAD'
      ? READ_TIMEOUT_MS
      : isLongTicketWrite
        ? TICKET_WRITE_TIMEOUT_MS
        : WRITE_TIMEOUT_MS;
  return next(req).pipe(
    timeout(timeoutMs),
    catchError((err) => {
      if (err instanceof TimeoutError) {
        return throwError(
          () =>
            new HttpErrorResponse({
              error: { detail: 'Tiempo de espera agotado. El servidor puede estar despertando.' },
              status: 0,
              statusText: 'Timeout',
              url: req.url,
            })
        );
      }
      return throwError(() => err);
    })
  );
};
