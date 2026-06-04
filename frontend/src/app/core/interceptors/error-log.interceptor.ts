import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { tap } from 'rxjs';
import { parseHttpError } from '../utils/http-error.util';

/** Registra en consola errores clasificados (usuario vs sistema vs red). */
export const errorLogInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    tap({
      error: (err) => {
        if (err instanceof HttpErrorResponse && err.status >= 400) {
          const parsed = parseHttpError(err, `${req.method} ${req.url}`);
          const level = parsed.kind === 'user' ? 'warn' : 'error';
          console[level](parsed.logLine, { parsed, raw: err.error });
        }
      },
    })
  );
};
