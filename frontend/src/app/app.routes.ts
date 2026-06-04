import { Routes } from '@angular/router';
import { ShellComponent } from './layout/shell/shell.component';

export const routes: Routes = [
  {
    path: '',
    component: ShellComponent,
    children: [
      { path: '', loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent) },
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
        path: 'perfil',
        loadComponent: () => import('./features/profile/profile.component').then((m) => m.ProfileComponent),
      },
      {
        path: 'validar',
        loadComponent: () => import('./features/validation/validation.component').then((m) => m.ValidationComponent),
      },
      {
        path: 'admin',
        loadComponent: () =>
          import('./features/admin/admin-dashboard.component').then((m) => m.AdminDashboardComponent),
      },
      {
        path: 'coleccion',
        loadComponent: () => import('./features/loyalty/collectibles.component').then((m) => m.CollectiblesComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
