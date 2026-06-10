import { Routes } from '@angular/router';
import { authGuard, roleGuard } from './core/guards/auth.guard';
import { ShellComponent } from './layout/shell/shell.component';

export const routes: Routes = [
  {
    path: '',
    component: ShellComponent,
    children: [
      { path: '', redirectTo: 'eventos', pathMatch: 'full' },
      { path: 'inicio', loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent) },
      {
        path: 'eventos',
        loadComponent: () => import('./features/events/events-list.component').then((m) => m.EventsListComponent),
      },
      {
        path: 'eventos/:id',
        loadComponent: () => import('./features/events/event-detail.component').then((m) => m.EventDetailComponent),
      },
      {
        path: 'ingresar',
        loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
      },
      {
        path: 'registro',
        loadComponent: () => import('./features/auth/register.component').then((m) => m.RegisterComponent),
      },
      {
        path: 'verificar-email',
        loadComponent: () => import('./features/auth/verify-email.component').then((m) => m.VerifyEmailComponent),
      },
      {
        path: 'olvide-contrasena',
        loadComponent: () =>
          import('./features/auth/forgot-password.component').then((m) => m.ForgotPasswordComponent),
      },
      {
        path: 'restablecer-contrasena',
        loadComponent: () =>
          import('./features/auth/reset-password.component').then((m) => m.ResetPasswordComponent),
      },
      {
        path: 'compra/resultado',
        canActivate: [authGuard],
        loadComponent: () =>
          import('./features/payments/purchase-result.component').then((m) => m.PurchaseResultComponent),
      },
      {
        path: 'perfil',
        canActivate: [authGuard],
        loadComponent: () => import('./features/profile/profile.component').then((m) => m.ProfileComponent),
      },
      {
        path: 'validar',
        canActivate: [authGuard, roleGuard(['validator', 'admin'])],
        loadComponent: () => import('./features/validation/validation.component').then((m) => m.ValidationComponent),
      },
      {
        path: 'admin',
        canActivate: [authGuard, roleGuard(['admin'])],
        loadComponent: () =>
          import('./features/admin/admin-dashboard.component').then((m) => m.AdminDashboardComponent),
      },
      {
        path: 'coleccion',
        canActivate: [authGuard],
        loadComponent: () => import('./features/loyalty/collectibles.component').then((m) => m.CollectiblesComponent),
      },
      {
        path: 'vender',
        canActivate: [authGuard, roleGuard(['seller', 'admin'])],
        loadComponent: () => import('./features/seller/seller-sell.component').then((m) => m.SellerSellComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
