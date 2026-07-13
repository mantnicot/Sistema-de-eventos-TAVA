import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { PreloadAllModules, provideRouter, withPreloading, withViewTransitions } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';

import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { errorLogInterceptor } from './core/interceptors/error-log.interceptor';
import { retryInterceptor } from './core/interceptors/retry.interceptor';
import { timeoutInterceptor } from './core/interceptors/timeout.interceptor';
import { tokenRefreshInterceptor } from './core/interceptors/token-refresh.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes, withViewTransitions(), withPreloading(PreloadAllModules)),
    provideHttpClient(
      withInterceptors([
        authInterceptor,
        retryInterceptor,
        timeoutInterceptor,
        tokenRefreshInterceptor,
        errorLogInterceptor,
      ])
    ),
    provideAnimationsAsync(),
  ],
};
