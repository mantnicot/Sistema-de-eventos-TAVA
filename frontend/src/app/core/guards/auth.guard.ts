import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isLoggedIn()) return true;
  return router.createUrlTree(['/ingresar'], { queryParams: { returnUrl: state.url } });
};

export const roleGuard = (roles: Array<'general' | 'admin' | 'organizer' | 'validator' | 'seller'>): CanActivateFn => {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (!auth.isLoggedIn()) {
      return router.createUrlTree(['/ingresar']);
    }
    if (auth.isPlatformAdmin()) return true;
    const role = auth.user()?.role;
    if (!role || !roles.includes(role)) {
      return router.createUrlTree(['/']);
    }
    return true;
  };
};
