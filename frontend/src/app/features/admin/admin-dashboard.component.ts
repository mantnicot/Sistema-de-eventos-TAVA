import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { SiteAppearance, SiteSettingsService } from '../../core/services/site-settings.service';
import { TavaFileUploadComponent } from '../../shared/components/tava-file-upload/tava-file-upload.component';
import { TavaEvent, TheatricalDetails } from '../../core/models/event.model';

interface Kpis {
  eventos_activos: number;
  boletas_vendidas: number;
  ingresos: number;
  asistentes: number;
  conversion_porcentaje: number;
}

interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  email_verified: boolean;
  is_active: boolean;
}

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [DecimalPipe, FormsModule, TavaFileUploadComponent],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.scss',
})
export class AdminDashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);
  private readonly site = inject(SiteSettingsService);

  readonly tab = signal<'kpis' | 'events' | 'users' | 'appearance'>('kpis');
  readonly kpis = signal<Kpis | null>(null);
  readonly adminEvents = signal<TavaEvent[]>([]);
  readonly users = signal<AdminUser[]>([]);
  readonly editingId = signal<string | null>(null);

  roleEmail = '';
  rolePick = 'seller';
  castInput = '';

  theatrical: TheatricalDetails = {};
  eventForm = {
    name: '',
    description: '',
    category: 'Teatro',
    event_date: '',
    event_time: '19:30',
    city: 'Bogotá',
    address: '',
    capacity: 100,
    status: 'borrador',
    main_image_url: '',
    trailer_url: '',
  };

  appearanceForm = { hero_video_url: '', hero_video_enabled: true };

  ngOnInit(): void {
    if (!this.auth.isAdmin()) {
      this.router.navigate(['/']);
      return;
    }
    this.loadKpis();
    this.loadAdminEvents();
    this.loadUsers();
    const app = this.site.appearance();
    if (app) {
      this.appearanceForm = { ...app };
    } else {
      this.site.loadAppearance();
      setTimeout(() => {
        const a = this.site.appearance();
        if (a) this.appearanceForm = { ...a };
      }, 500);
    }
  }

  loadKpis(): void {
    this.api.get<Kpis>('/dashboard/kpis').subscribe({ next: (k) => this.kpis.set(k) });
  }

  loadAdminEvents(): void {
    this.api.get<TavaEvent[]>('/events/admin/all').subscribe({ next: (e) => this.adminEvents.set(e) });
  }

  loadUsers(): void {
    this.api.get<AdminUser[]>('/users').subscribe({ next: (u) => this.users.set(u) });
  }

  resetEventForm(): void {
    this.editingId.set(null);
    this.castInput = '';
    this.theatrical = {};
    this.eventForm = {
      name: '',
      description: '',
      category: 'Teatro',
      event_date: '',
      event_time: '19:30',
      city: 'Bogotá',
      address: '',
      capacity: 100,
      status: 'borrador',
      main_image_url: '',
      trailer_url: '',
    };
  }

  editEvent(ev: TavaEvent): void {
    this.editingId.set(ev.id);
    this.eventForm = {
      name: ev.name,
      description: ev.description,
      category: ev.category,
      event_date: ev.event_date,
      event_time: ev.event_time?.slice(0, 5) ?? '19:30',
      city: ev.city,
      address: ev.address,
      capacity: ev.capacity,
      status: ev.status,
      main_image_url: ev.main_image_url ?? '',
      trailer_url: ev.trailer_url ?? '',
    };
    this.theatrical = { ...(ev.theatrical_details ?? {}) };
    this.castInput = (this.theatrical.cast ?? []).join(', ');
  }

  saveEvent(): void {
    const cast = this.castInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const body = {
      ...this.eventForm,
      theatrical_details: { ...this.theatrical, cast },
    };
    const id = this.editingId();
    const req = id
      ? this.api.patch<TavaEvent>(`/events/${id}`, body)
      : this.api.post<TavaEvent>('/events', body);
    req.subscribe({
      next: () => {
        this.notify.success('Eventos', id ? 'Evento actualizado' : 'Evento creado');
        this.resetEventForm();
        this.loadAdminEvents();
      },
      error: () => this.notify.error('Eventos', 'No se pudo guardar el evento'),
    });
  }

  assignRole(): void {
    const user = this.users().find((u) => u.email.toLowerCase() === this.roleEmail.toLowerCase());
    if (!user) {
      this.notify.warning('Usuarios', 'Primero carga la lista y usa un correo existente');
      return;
    }
    this.patchRole(user.id, this.rolePick);
  }

  changeRole(userId: string, ev: Event): void {
    const role = (ev.target as HTMLSelectElement).value;
    this.patchRole(userId, role);
  }

  private patchRole(userId: string, role: string): void {
    this.api.patch<AdminUser>(`/users/${userId}/role`, { role }).subscribe({
      next: () => {
        this.notify.success('Usuarios', 'Rol actualizado');
        this.loadUsers();
      },
      error: () => this.notify.error('Usuarios', 'No se pudo cambiar el rol'),
    });
  }

  addGalleryMedia(eventId: string, url: string, mediaType: string): void {
    this.api
      .post(`/events/${eventId}/media`, { media_type: mediaType, url, sort_order: 0 })
      .subscribe({
        next: () => this.notify.success('Galería', 'Archivo añadido al evento'),
        error: () => this.notify.error('Galería', 'No se pudo añadir el archivo'),
      });
  }

  deleteEvent(ev: TavaEvent): void {
    this.notify.confirm('Eliminar evento', `¿Eliminar "${ev.name}"? Esta acción no se puede deshacer.`, () => {
      this.api.delete(`/events/${ev.id}`).subscribe({
        next: () => {
          this.notify.success('Eventos', 'Evento eliminado');
          if (this.editingId() === ev.id) this.resetEventForm();
          this.loadAdminEvents();
        },
        error: () => this.notify.error('Eventos', 'No se pudo eliminar (puede tener boletas)'),
      });
    });
  }

  deleteUser(u: AdminUser): void {
    this.notify.confirm('Eliminar usuario', `¿Eliminar a ${u.full_name}?`, () => {
      this.api.delete(`/users/${u.id}`).subscribe({
        next: () => {
          this.notify.success('Usuarios', 'Usuario eliminado');
          this.loadUsers();
        },
        error: () => this.notify.error('Usuarios', 'No se pudo eliminar el usuario'),
      });
    });
  }

  saveAppearance(): void {
    this.site.updateAppearance(this.appearanceForm).subscribe({
      next: (a: SiteAppearance) => {
        this.site.appearance.set(a);
        this.notify.success('Apariencia', 'Video de fondo actualizado');
      },
      error: () => this.notify.error('Apariencia', 'No se pudo guardar'),
    });
  }
}
