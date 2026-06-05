import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { SiteAppearance, SiteSettingsService } from '../../core/services/site-settings.service';
import {
  GALLERY_IMAGE_SPEC,
  GALLERY_VIDEO_SPEC,
  IMAGE_EVENT_SPEC,
  VIDEO_HERO_SPEC,
  VIDEO_TRAILER_SPEC,
} from '../../core/constants/media-upload-specs.const';
import { TavaFileUploadComponent } from '../../shared/components/tava-file-upload/tava-file-upload.component';
import { TavaTicketPreviewComponent } from '../../shared/components/tava-ticket-preview/tava-ticket-preview.component';
import { TavaEvent, TavaEventDetail, TheatricalDetails } from '../../core/models/event.model';
import { TicketKind, TicketTypeDraft } from '../../core/models/ticket-type.model';

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
  imports: [DecimalPipe, FormsModule, TavaFileUploadComponent, TavaTicketPreviewComponent],
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
  readonly imageEventSpec = IMAGE_EVENT_SPEC;
  readonly videoTrailerSpec = VIDEO_TRAILER_SPEC;
  readonly galleryImageSpec = GALLERY_IMAGE_SPEC;
  readonly galleryVideoSpec = GALLERY_VIDEO_SPEC;
  readonly videoHeroSpec = VIDEO_HERO_SPEC;
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

  ticketTypesDraft: TicketTypeDraft[] = [];
  ticketTypesTouched = false;
  previewTypeIndex = 0;
  readonly ticketKinds: { value: TicketKind; label: string }[] = [
    { value: 'individual', label: 'Individual' },
    { value: 'grupal', label: 'Grupal' },
    { value: 'vip', label: 'VIP' },
    { value: 'promocional', label: 'Promocional' },
    { value: 'cortesia', label: 'Cortesía' },
  ];

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

  isCurrentUser(u: AdminUser): boolean {
    return u.id === this.auth.user()?.id;
  }

  loadKpis(): void {
    this.notify.loadingTheatrical('Cartelera del director', 'admin');
    this.api.get<Kpis>('/dashboard/kpis').subscribe({
      next: (k) => {
        this.notify.hide();
        this.kpis.set(k);
      },
      error: () => this.notify.hide(),
    });
  }

  loadAdminEvents(): void {
    this.api.get<TavaEvent[]>('/events/admin/all').subscribe({ next: (e) => this.adminEvents.set(e) });
  }

  loadUsers(): void {
    this.api.get<AdminUser[]>('/users').subscribe({ next: (u) => this.users.set(u) });
  }

  ticketsAllocated(): number {
    return this.ticketTypesDraft.reduce((s, t) => s + (t.quantity_available || 0), 0);
  }

  ticketsRemaining(): number {
    const cap = this.eventForm.capacity || 0;
    return Math.max(0, cap - this.ticketsAllocated());
  }

  capacityExceeded(): boolean {
    const cap = this.eventForm.capacity || 0;
    return cap > 0 && this.ticketsAllocated() > cap;
  }

  previewType(): TicketTypeDraft | null {
    if (!this.ticketTypesDraft.length) return null;
    const idx = Math.min(this.previewTypeIndex, this.ticketTypesDraft.length - 1);
    return this.ticketTypesDraft[idx];
  }

  addTicketType(): void {
    const remaining = this.ticketsRemaining() || this.eventForm.capacity || 50;
    this.ticketTypesDraft.push({
      name: 'General',
      kind: 'individual',
      price: 45000,
      quantity_available: Math.min(remaining, 50),
      benefits: '',
    });
    this.ticketTypesTouched = true;
    this.previewTypeIndex = this.ticketTypesDraft.length - 1;
  }

  addSuggestedTicketTypes(): void {
    const cap = this.eventForm.capacity || 100;
    const vipQty = Math.max(1, Math.floor(cap * 0.2));
    const genQty = Math.max(0, cap - vipQty);
    this.ticketTypesDraft = [
      {
        name: 'VIP',
        kind: 'vip',
        price: 120000,
        quantity_available: vipQty,
        benefits: 'Mejor ubicación y acceso preferencial',
      },
      {
        name: 'General',
        kind: 'individual',
        price: 55000,
        quantity_available: genQty,
        benefits: 'Entrada estándar',
      },
    ];
    this.ticketTypesTouched = true;
    this.previewTypeIndex = 0;
  }

  removeTicketType(index: number): void {
    this.ticketTypesDraft.splice(index, 1);
    this.ticketTypesTouched = true;
    if (this.previewTypeIndex >= this.ticketTypesDraft.length) {
      this.previewTypeIndex = Math.max(0, this.ticketTypesDraft.length - 1);
    }
  }

  onTicketDraftChange(): void {
    this.ticketTypesTouched = true;
  }

  resetEventForm(): void {
    this.editingId.set(null);
    this.castInput = '';
    this.ticketTypesDraft = [];
    this.ticketTypesTouched = false;
    this.previewTypeIndex = 0;
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
    this.ticketTypesDraft = [];
    this.ticketTypesTouched = false;
    this.previewTypeIndex = 0;
    this.api.get<TavaEventDetail>(`/events/${ev.id}`).subscribe({
      next: (detail) => {
        this.ticketTypesDraft = (detail.ticket_types ?? []).map((t) => ({
          id: t.id,
          name: t.name,
          kind: t.kind as TicketKind,
          price: Number(t.price),
          quantity_available: t.quantity_available,
          benefits: t.benefits ?? '',
        }));
      },
    });
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
    if (this.capacityExceeded()) {
      this.notify.warning(
        'Aforo',
        `Los cupos (${this.ticketsAllocated()}) superan la capacidad (${this.eventForm.capacity}).`
      );
      return;
    }
    this.notify.loadingTheatrical('Guardando obra', 'admin');
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
      next: (saved) => {
        const eventId = id ?? saved.id;
        const finish = () => {
          this.notify.hide();
          this.notify.success('Eventos', id ? 'Evento actualizado' : 'Evento creado');
          this.resetEventForm();
          this.loadAdminEvents();
        };
        const shouldSync =
          this.ticketTypesDraft.length > 0 || (this.ticketTypesTouched && !!id);
        if (shouldSync) {
          this.syncTicketTypes(eventId, finish);
        } else {
          finish();
        }
      },
      error: () => {
        this.notify.hide();
        this.notify.error('Eventos', 'No se pudo guardar el evento');
      },
    });
  }

  private syncTicketTypes(eventId: string, onDone: () => void): void {
    const payload = {
      ticket_types: this.ticketTypesDraft.map((t) => ({
        id: t.id ?? null,
        name: t.name,
        kind: t.kind,
        price: t.price,
        quantity_available: t.quantity_available,
        benefits: t.benefits || null,
      })),
    };
    this.api.put(`/events/${eventId}/ticket-types`, payload).subscribe({
      next: () => onDone(),
      error: (err) => {
        this.notify.hide();
        const msg = err?.error?.detail ?? 'No se pudo guardar la boletería';
        this.notify.error('Boletería', typeof msg === 'string' ? msg : 'Revisa cupos y precios');
      },
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
      this.notify.loadingTheatrical('Retirando del cartel', 'delete');
      this.api.delete(`/events/${ev.id}`).subscribe({
        next: () => {
          this.notify.hide();
          this.notify.success('Eventos', 'Evento eliminado');
          if (this.editingId() === ev.id) this.resetEventForm();
          this.loadAdminEvents();
        },
        error: () => {
          this.notify.hide();
          this.notify.error('Eventos', 'No se pudo eliminar (puede tener boletas)');
        },
      });
    });
  }

  deleteUser(u: AdminUser): void {
    if (this.isCurrentUser(u)) {
      this.notify.warning(
        '¡Alto en escena!',
        'El director no puede eliminarse a sí mismo del reparto. Pide a otro admin si hace falta.'
      );
      return;
    }
    this.notify.confirm('Eliminar usuario', `¿Eliminar a ${u.full_name}?`, () => {
      this.notify.loadingTheatrical('Fuera de escena', 'delete');
      this.api.delete(`/users/${u.id}`).subscribe({
        next: () => {
          this.notify.hide();
          this.notify.success('Usuarios', 'Usuario eliminado');
          this.loadUsers();
        },
        error: () => {
          this.notify.hide();
          this.notify.error('Usuarios', 'No se pudo eliminar el usuario');
        },
      });
    });
  }

  saveAppearance(): void {
    this.notify.loadingTheatrical('Ajustando el telón', 'upload');
    this.site.updateAppearance(this.appearanceForm).subscribe({
      next: (a: SiteAppearance) => {
        this.notify.hide();
        this.site.appearance.set(a);
        this.notify.success('Apariencia', 'Video de fondo actualizado');
      },
      error: () => {
        this.notify.hide();
        this.notify.error('Apariencia', 'No se pudo guardar');
      },
    });
  }
}
