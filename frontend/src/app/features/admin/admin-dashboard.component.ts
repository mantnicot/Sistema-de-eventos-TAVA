import { Component, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
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
import { TavaEvent, TavaEventDetail, TheatricalDetails, CastMember } from '../../core/models/event.model';
import { TicketKind, TicketTypeDraft } from '../../core/models/ticket-type.model';
import { resolveMediaUrl } from '../../core/utils/media-url.util';
import { DEFAULT_SEATING, SeatingConfig } from '../../core/models/seating.model';

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

interface AttendeeItem {
  ticket_id: string;
  holder_name: string | null;
  ticket_code: string | null;
  is_used: boolean;
  is_cancelled: boolean;
  used_at: string | null;
}

interface AttendeesResponse {
  event_id: string;
  event_name: string;
  ingresados: number;
  boletas_vendidas: number;
  pendientes_ingreso: number;
  attendees: AttendeeItem[];
}

interface AttendeeNotification {
  notified?: boolean;
  reason?: string;
  changes?: string[];
  emails_sent?: number;
  tickets_regenerated?: number;
  tickets_affected?: number;
  email_error?: string | null;
}

interface EventUpdateResponse extends TavaEvent {
  attendee_notification?: AttendeeNotification;
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
  castMembers: CastMember[] = [{ name: '', photo_url: '', role: '' }];
  staffValidatorIds: string[] = [];
  staffSellerIds: string[] = [];
  staffSearch = '';
  readonly attendeesData = signal<AttendeesResponse | null>(null);
  readonly attendeesLoading = signal(false);
  broadcastSubject = '';
  broadcastMessage = '';
  cancelNotifyHolder = true;
  seatingDraft: SeatingConfig = structuredClone(DEFAULT_SEATING);

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

  filteredStaffUsers(): AdminUser[] {
    const q = this.staffSearch.trim().toLowerCase();
    const list = this.users().filter((u) => u.role !== 'admin');
    if (!q) return list;
    return list.filter(
      (u) =>
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        u.role.toLowerCase().includes(q)
    );
  }

  isStaffValidator(id: string): boolean {
    return this.staffValidatorIds.includes(id);
  }

  isStaffSeller(id: string): boolean {
    return this.staffSellerIds.includes(id);
  }

  toggleStaffValidatorBtn(id: string): void {
    if (this.staffValidatorIds.includes(id)) {
      this.staffValidatorIds = this.staffValidatorIds.filter((x) => x !== id);
    } else {
      this.staffValidatorIds = [...this.staffValidatorIds, id];
    }
  }

  toggleStaffSellerBtn(id: string): void {
    if (this.staffSellerIds.includes(id)) {
      this.staffSellerIds = this.staffSellerIds.filter((x) => x !== id);
    } else {
      this.staffSellerIds = [...this.staffSellerIds, id];
    }
  }

  clearStaffUser(id: string): void {
    this.staffValidatorIds = this.staffValidatorIds.filter((x) => x !== id);
    this.staffSellerIds = this.staffSellerIds.filter((x) => x !== id);
  }

  saveStaffOnly(): void {
    const eventId = this.editingId();
    if (!eventId) {
      this.notify.warning('Personal', 'Primero guarda el evento o selecciona uno para editar');
      return;
    }
    this.notify.loadingTheatrical('Asignando personal', 'admin');
    this.api
      .put(`/events/${eventId}/staff`, {
        validator_ids: this.staffValidatorIds,
        seller_ids: this.staffSellerIds,
      })
      .subscribe({
        next: () => {
          this.notify.hide();
          this.notify.success('Personal', 'Asignación guardada');
        },
        error: () => {
          this.notify.hide();
          this.notify.error('Personal', 'No se pudo guardar la asignación');
        },
      });
  }

  downloadReport(format: 'pdf' | 'xlsx'): void {
    const path = format === 'pdf' ? '/dashboard/report/pdf' : '/dashboard/report/xlsx';
    const filename = format === 'pdf' ? 'tava-metricas.pdf' : 'tava-metricas.xlsx';
    this.notify.loadingTheatrical('Generando reporte', 'admin');
    this.api.downloadBlob(path).subscribe({
      next: (blob) => {
        this.notify.hide();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        this.notify.success('Reporte', 'Descarga iniciada');
      },
      error: () => {
        this.notify.hide();
        this.notify.error('Reporte', 'No se pudo generar el archivo');
      },
    });
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

  artistPhotoUrl(url: string | undefined): string {
    return url ? resolveMediaUrl(url) : '';
  }

  addArtist(): void {
    this.castMembers.push({ name: '', photo_url: '', role: '' });
  }

  removeArtist(index: number): void {
    this.castMembers.splice(index, 1);
    if (!this.castMembers.length) {
      this.castMembers.push({ name: '', photo_url: '', role: '' });
    }
  }

  onArtistPhoto(index: number, url: string): void {
    if (this.castMembers[index]) {
      this.castMembers[index].photo_url = url;
    }
  }

  resetEventForm(): void {
    this.editingId.set(null);
    this.castMembers = [{ name: '', photo_url: '', role: '' }];
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
    this.staffValidatorIds = [];
    this.staffSellerIds = [];
    this.attendeesData.set(null);
    this.broadcastSubject = '';
    this.broadcastMessage = '';
    this.seatingDraft = structuredClone(DEFAULT_SEATING);
  }

  loadAttendees(eventId: string): void {
    this.attendeesLoading.set(true);
    this.api.get<AttendeesResponse>(`/validation/attendees/${eventId}`).subscribe({
      next: (data) => {
        this.attendeesData.set(data);
        this.attendeesLoading.set(false);
      },
      error: () => {
        this.attendeesData.set(null);
        this.attendeesLoading.set(false);
      },
    });
  }

  attendeeStatusLabel(a: AttendeeItem): string {
    if (a.is_cancelled) return 'Cancelada';
    if (a.is_used) return 'Usada';
    return 'Válida';
  }

  cancelAttendeeTicket(ticketId: string): void {
    this.notify.confirm(
      'Cancelar boleta',
      'La boleta quedará invalidada y se liberará el cupo si aplica. ¿Continuar?',
      () => {
        this.notify.loadingTheatrical('Cancelando boleta', 'admin');
        this.api
          .post<{ email_sent: boolean }>(`/tickets/admin/${ticketId}/cancel`, {
            notify_holder: this.cancelNotifyHolder,
          })
          .subscribe({
            next: (res) => {
              this.notify.hide();
              const extra = res.email_sent ? ' Se avisó al titular por correo.' : '';
              this.notify.success('Boletas', `Boleta cancelada.${extra}`);
              const id = this.editingId();
              if (id) this.loadAttendees(id);
            },
            error: (err) => {
              this.notify.hide();
              this.notify.error('Boletas', err.error?.detail ?? 'No se pudo cancelar');
            },
          });
      }
    );
  }

  sendBroadcastEmail(): void {
    const id = this.editingId();
    if (!id) return;
    const subject = this.broadcastSubject.trim();
    const message = this.broadcastMessage.trim();
    if (subject.length < 3 || message.length < 10) {
      this.notify.warning('Correo', 'Escribe un asunto (mín. 3) y un mensaje (mín. 10 caracteres).');
      return;
    }
    this.notify.confirm(
      'Enviar correo',
      'Se enviará a todos los compradores con boletas pagadas de este evento. ¿Continuar?',
      () => {
        this.notify.loadingTheatrical('Enviando correos', 'admin');
        this.api
          .post<{ sent: number; recipients: number }>(`/events/${id}/broadcast-email`, {
            subject,
            message,
          })
          .subscribe({
            next: (res) => {
              this.notify.hide();
              if (res.sent > 0) {
                this.notify.success('Correo', `Enviados ${res.sent} de ${res.recipients} destinatarios.`);
              } else {
                const err = (res as { email_error?: string }).email_error;
                this.notify.error(
                  'Correo',
                  err ?? 'No se envió ningún correo. Verifica BREVO_SENDER_EMAIL en Render.'
                );
              }
              this.broadcastSubject = '';
              this.broadcastMessage = '';
            },
            error: (err) => {
              this.notify.hide();
              this.notify.error('Correo', err.error?.detail ?? 'No se pudo enviar');
            },
          });
      }
    );
  }

  private showAttendeeNotification(n: AttendeeNotification): void {
    if (n.notified) {
      this.notify.success(
        'Asistentes avisados',
        `Cambios en el evento: ${n.emails_sent ?? 0} correo(s), ${n.tickets_regenerated ?? 0} boleta(s) regenerada(s).`
      );
      return;
    }
    if (n.reason === 'sin_cambios_relevantes') return;
    if (n.reason === 'sin_boletas_vendidas') return;
    const detail = n.email_error ? ` ${n.email_error}` : '';
    if (n.reason === 'correo_no_configurado' || n.reason === 'envio_fallido') {
      this.notify.warning(
        'Correo no enviado',
        `Hubo cambios pero no se pudo avisar a los asistentes.${detail || ' Revisa BREVO_SENDER_EMAIL en Render.'}`
      );
    }
  }

  testAdminEmail(): void {
    this.notify.loadingTheatrical('Enviando prueba', 'admin');
    this.api.post<{ success: boolean; message: string }>('/dashboard/test-email', {}).subscribe({
      next: (res) => {
        this.notify.hide();
        if (res.success) {
          this.notify.success('Correo', res.message);
        } else {
          this.notify.error('Correo', res.message);
        }
      },
      error: (err) => {
        this.notify.hide();
        this.notify.error('Correo', err.error?.message ?? err.error?.detail ?? 'No se pudo enviar');
      },
    });
  }

  saveEventSeating(): void {
    const id = this.editingId();
    if (!id) return;
    this.notify.loadingTheatrical('Generando silletería', 'admin');
    this.api.put<{ seats_created?: number }>(`/events/${id}/seating`, { seating: this.seatingDraft }).subscribe({
      next: (res) => {
        this.notify.hide();
        this.notify.success(
          'Silletería',
          `Mapa guardado${res.seats_created != null ? ` (${res.seats_created} sillas)` : ''}.`
        );
      },
      error: (err) => {
        this.notify.hide();
        this.notify.error('Silletería', err.error?.detail ?? 'No se pudo guardar');
      },
    });
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
    const td = ev.theatrical_details;
    if (td?.cast_members?.length) {
      this.castMembers = td.cast_members.map((m) => ({ ...m }));
    } else if (td?.cast?.length) {
      this.castMembers = td.cast.map((name) => ({ name, photo_url: '', role: '' }));
    } else {
      this.castMembers = [{ name: '', photo_url: '', role: '' }];
    }
    this.staffValidatorIds = [];
    this.staffSellerIds = [];
    const seating = ev.theatrical_details?.seating;
    this.seatingDraft = seating
      ? {
          ...DEFAULT_SEATING,
          ...seating,
          blocks: seating.blocks?.length ? seating.blocks : DEFAULT_SEATING.blocks,
        }
      : structuredClone(DEFAULT_SEATING);
    this.api
      .get<{ validator_ids: string[]; seller_ids: string[] }>(`/events/${ev.id}/staff`)
      .subscribe({
        next: (staff) => {
          this.staffValidatorIds = (staff.validator_ids ?? []).map(String);
          this.staffSellerIds = (staff.seller_ids ?? []).map(String);
        },
      });
    this.loadAttendees(ev.id);
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
    const members = this.castMembers
      .map((m) => ({
        name: m.name.trim(),
        photo_url: m.photo_url?.trim() || undefined,
        role: m.role?.trim() || undefined,
      }))
      .filter((m) => m.name);
    const body = {
      ...this.eventForm,
      theatrical_details: {
        ...this.theatrical,
        cast: members.map((m) => m.name),
        cast_members: members,
        seating: this.seatingDraft,
      },
    };
    const id = this.editingId();
    const req = id
      ? this.api.patch<EventUpdateResponse>(`/events/${id}`, body)
      : this.api.post<TavaEvent>('/events', body);
    req.subscribe({
      next: (saved) => {
        const eventId = id ?? saved.id;
        const attendeeNotification = id
          ? (saved as EventUpdateResponse).attendee_notification
          : undefined;
        const finish = () => {
          if (id) {
            this.saveEventStaff(eventId, () => {
              this.notify.hide();
              this.notify.success('Eventos', 'Evento actualizado');
              if (attendeeNotification) {
                this.showAttendeeNotification(attendeeNotification);
              }
              this.resetEventForm();
              this.loadAdminEvents();
            });
          } else {
            this.notify.hide();
            this.notify.success('Eventos', 'Evento creado');
            this.resetEventForm();
            this.loadAdminEvents();
          }
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

  private saveEventStaff(eventId: string, onDone: () => void): void {
    this.api
      .put(`/events/${eventId}/staff`, {
        validator_ids: this.staffValidatorIds,
        seller_ids: this.staffSellerIds,
      })
      .subscribe({
        next: () => onDone(),
        error: () => {
          this.notify.hide();
          this.notify.warning('Personal', 'Evento guardado pero no se pudo asignar el personal');
          this.resetEventForm();
          this.loadAdminEvents();
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
