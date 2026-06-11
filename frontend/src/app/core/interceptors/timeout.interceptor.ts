import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError, timeout, TimeoutError } from 'rxjs';

/** Evita peticiones colgadas indefinidamente (Render cold start). */
const API_TIMEOUT_MS = 35000;

export const timeoutInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url.includes('/uploads/') || req.responseType === 'blob') {
    return next(req);
  }
  return next(req).pipe(
    timeout(API_TIMEOUT_MS),
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
