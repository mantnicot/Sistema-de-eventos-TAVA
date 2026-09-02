import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { catchError, finalize, of, timeout } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { ApiWarmupService } from '../../core/services/api-warmup.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { SiteAppearance, SiteSettingsService } from '../../core/services/site-settings.service';
import {
  GALLERY_IMAGE_SPEC,
  GALLERY_VIDEO_SPEC,
  IMAGE_EVENT_SPEC,
  VIDEO_LOADER_SPEC,
  VIDEO_TRAILER_SPEC,
} from '../../core/constants/media-upload-specs.const';
import { TavaFileUploadComponent } from '../../shared/components/tava-file-upload/tava-file-upload.component';
import { TavaListSearchComponent } from '../../shared/components/tava-list-search/tava-list-search.component';
import { AdminUsersPanelComponent } from './admin-users-panel.component';
import { TavaEvent, TavaEventDetail, TheatricalDetails, CastMember } from '../../core/models/event.model';
import { TicketKind, TicketTypeDraft } from '../../core/models/ticket-type.model';
import { resolveMediaUrl } from '../../core/utils/media-url.util';
import { matchesSearch } from '../../core/utils/list-search.util';
import { mergeSeatingPreview, applyBlockTicketType, applySeatTicketType } from '../../core/utils/seating-preview.util';
import {
  countLayoutSeats,
  countSeatsByTicketType,
  DEFAULT_SEATING,
  newSeatingBlock,
  SeatMapItem,
  SeatingConfig,
  SeatTicketTypeOption,
} from '../../core/models/seating.model';

interface Kpis {
  scope?: 'general' | 'event';
  event_id?: string | null;
  event_name?: string | null;
  event_date?: string | null;
  event_status?: string | null;
  capacity?: number;
  eventos_activos: number;
  boletas_vendidas: number;
  ingresos: number;
  asistentes: number;
  pendientes_ingreso?: number;
  ocupacion_porcentaje?: number;
  ordenes_totales?: number;
  ordenes_pagadas?: number;
  conversion_porcentaje: number;
}

interface AttendeeItem {
  ticket_id: string;
  order_id: string;
  holder_name: string | null;
  recipient_name: string | null;
  recipient_email: string | null;
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

interface ReviewNotification {
  notified?: boolean;
  reason?: string;
  emails_sent?: number;
  recipients?: number;
  email_error?: string | null;
}

interface EventUpdateResponse extends TavaEvent {
  attendee_notification?: AttendeeNotification;
  review_notification?: ReviewNotification;
}

const ADMIN_REQUEST_TIMEOUT_MS = 12000;
const ADMIN_EVENTS_TIMEOUT_MS = 55000;

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [DecimalPipe, FormsModule, TavaFileUploadComponent, AdminUsersPanelComponent, TavaListSearchComponent],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.scss',
})
export class AdminDashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly warmup = inject(ApiWarmupService);
  private readonly notify = inject(NotificationService);
  private readonly site = inject(SiteSettingsService);

  readonly isPlatformAdmin = computed(() => this.auth.isPlatformAdmin());
  readonly tab = signal<'kpis' | 'events' | 'review' | 'users' | 'appearance'>('kpis');
  readonly imageEventSpec = IMAGE_EVENT_SPEC;
  readonly videoTrailerSpec = VIDEO_TRAILER_SPEC;
  readonly galleryImageSpec = GALLERY_IMAGE_SPEC;
  readonly galleryVideoSpec = GALLERY_VIDEO_SPEC;
  readonly videoLoaderSpec = VIDEO_LOADER_SPEC;
  readonly kpis = signal<Kpis | null>(null);
  readonly kpisLoading = signal(false);
  readonly adminEvents = signal<TavaEvent[]>([]);
  readonly editingId = signal<string | null>(null);
  readonly adminLoading = signal(true);
  readonly adminApiError = signal<string | null>(null);
  readonly adminEventsLoading = signal(false);
  readonly adminEventsError = signal<string | null>(null);
  readonly reviewQueue = signal<TavaEvent[]>([]);
  readonly reviewLoading = signal(false);
  rejectReasonText = '';
  readonly rejectingId = signal<string | null>(null);

  selectedReportEventId = '';
  castMembers: CastMember[] = [{ name: '', photo_url: '', role: '' }];
  readonly attendeesData = signal<AttendeesResponse | null>(null);
  readonly attendeesLoading = signal(false);
  readonly attendeesQuery = signal('');
  readonly eventsQuery = signal('');
  broadcastSubject = '';
  broadcastMessage = '';
  cancelNotifyHolder = true;
  seatingDraft: SeatingConfig = structuredClone(DEFAULT_SEATING);
  savedSeatingSeats: SeatMapItem[] = [];
  adminSeatPreviewSelected: string[] = [];
  seatingAssignTicketTypeId: string | null = null;

  theatrical: TheatricalDetails = {
    sale_mode: 'system',
    whatsapp_number: '',
    whatsapp_message: '',
  };
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

  appearanceForm = { loader_video_url: '', loader_video_enabled: true };

  ticketTypesDraft: TicketTypeDraft[] = [];
  ticketTypesTouched = false;
  private duplicateGalleryDraft: TavaEventDetail['gallery'] = [];
  readonly ticketKinds: { value: TicketKind; label: string }[] = [
    { value: 'individual', label: 'Individual' },
    { value: 'grupal', label: 'Grupal' },
    { value: 'vip', label: 'VIP' },
    { value: 'promocional', label: 'Promocional' },
    { value: 'cortesia', label: 'Cortesía' },
  ];

  readonly filteredAttendees = computed(() => {
    const data = this.attendeesData();
    if (!data) return [];
    return data.attendees.filter((a) =>
      matchesSearch(
        this.attendeesQuery(),
        a.holder_name,
        a.recipient_name,
        a.recipient_email,
        a.ticket_code,
        this.attendeeStatusLabel(a)
      )
    );
  });

  readonly filteredSidebarEvents = computed(() =>
    this.adminEvents().filter((ev) =>
      matchesSearch(this.eventsQuery(), ev.name, ev.city, ev.event_date, ev.category, ev.status)
    )
  );

  ngOnInit(): void {
    if (!this.isPlatformAdmin()) {
      this.tab.set('events');
    }
    void this.bootstrapAdmin();
  }

  bootstrapAdmin(): void {
    this.adminLoading.set(true);
    this.adminApiError.set(null);
    this.adminEventsError.set(null);
    void this.warmup.wake().finally(() => {
      if (!this.adminEvents().length && !this.adminEventsLoading()) this.loadAdminEvents();
    });
    this.loadAdminData();
  }

  private loadAdminData(): void {
    if (this.isPlatformAdmin()) {
      this.api
        .get<Kpis>('/dashboard/kpis')
        .pipe(
          timeout(ADMIN_REQUEST_TIMEOUT_MS),
          catchError(() => {
            this.adminApiError.set(
              'Algunos datos no cargaron a tiempo. Puedes entrar a Eventos o pulsar Reintentar.'
            );
            return of(null);
          }),
          finalize(() => {
            this.adminLoading.set(false);
            this.loadAppearanceForm();
          })
        )
        .subscribe((kpis) => {
          if (kpis) this.kpis.set(kpis);
        });
      this.loadReviewQueue();
    } else {
      this.adminLoading.set(false);
    }

    this.loadAdminEvents();
  }

  loadReviewQueue(): void {
    if (!this.isPlatformAdmin()) return;
    this.reviewLoading.set(true);
    this.api.get<TavaEvent[]>('/events/admin/review-queue').subscribe({
      next: (items) => {
        this.reviewQueue.set(items ?? []);
        this.reviewLoading.set(false);
      },
      error: () => {
        this.reviewQueue.set([]);
        this.reviewLoading.set(false);
      },
    });
  }

  approveEvent(ev: TavaEvent): void {
    this.api.patch<TavaEvent>(`/events/${ev.id}/review`, { action: 'approve', cartelera_visible: true }).subscribe({
      next: () => {
        this.notify.success('Revisión', `«${ev.name}» aprobado y visible en cartelera`);
        this.loadReviewQueue();
        this.loadAdminEvents();
      },
      error: (err) => this.notify.error('Revisión', err?.error?.detail ?? 'No se pudo aprobar'),
    });
  }

  rejectEvent(ev: TavaEvent): void {
    const reason = this.rejectReasonText.trim() || 'Revisión rechazada por el administrador';
    this.api.patch<TavaEvent>(`/events/${ev.id}/review`, { action: 'reject', rejection_reason: reason }).subscribe({
      next: () => {
        this.notify.success('Revisión', `«${ev.name}» rechazado`);
        this.rejectingId.set(null);
        this.rejectReasonText = '';
        this.loadReviewQueue();
        this.loadAdminEvents();
      },
      error: (err) => this.notify.error('Revisión', err?.error?.detail ?? 'No se pudo rechazar'),
    });
  }

  toggleCartelera(ev: TavaEvent, visible: boolean): void {
    this.api.patch<TavaEvent>(`/events/${ev.id}/cartelera`, { visible }).subscribe({
      next: () => {
        this.notify.success('Cartelera', visible ? `«${ev.name}» visible en cartelera` : `«${ev.name}» oculto de cartelera`);
        this.loadAdminEvents();
      },
      error: (err) => this.notify.error('Cartelera', err?.error?.detail ?? 'No se pudo actualizar'),
    });
  }

  submitForReview(): void {
    const id = this.editingId();
    if (!id) {
      this.notify.warning('Revisión', 'Guarda el evento antes de enviarlo a revisión');
      return;
    }
    this.api.post<EventUpdateResponse>(`/events/${id}/submit-review`, {}).subscribe({
      next: (res) => {
        const mail = res.review_notification;
        if (mail?.notified) {
          this.notify.success('Revisión', 'Evento enviado. Te avisamos al administrador por correo.');
        } else if (mail?.reason === 'correo_no_configurado') {
          this.notify.warning(
            'Revisión',
            'Evento enviado, pero el correo no está configurado en el servidor.'
          );
        } else if (mail && !mail.notified) {
          this.notify.warning('Revisión', 'Evento enviado, pero no se pudo notificar por correo.');
        } else {
          this.notify.success('Revisión', 'Evento enviado al administrador global');
        }
        this.loadAdminEvents();
      },
      error: (err) => this.notify.error('Revisión', err?.error?.detail ?? 'No se pudo enviar'),
    });
  }

  reviewStatusLabel(status?: string): string {
    if (status === 'aprobado') return 'Aprobado';
    if (status === 'rechazado') return 'Rechazado';
    return 'Pendiente';
  }

  private loadAppearanceForm(): void {
    const app = this.site.appearance();
    if (app) {
      this.appearanceForm = { ...app };
      return;
    }
    this.site.loadAppearance();
    setTimeout(() => {
      const a = this.site.appearance();
      if (a) this.appearanceForm = { ...a };
    }, 400);
  }

  downloadReport(format: 'pdf' | 'xlsx'): void {
    const basePath = format === 'pdf' ? '/dashboard/report/pdf' : '/dashboard/report/xlsx';
    const path = this.selectedReportEventId
      ? `${basePath}?event_id=${encodeURIComponent(this.selectedReportEventId)}`
      : basePath;
    const selectedEvent = this.adminEvents().find((event) => event.id === this.selectedReportEventId);
    const scopeName = selectedEvent
      ? selectedEvent.name.toLowerCase().replace(/[^a-z0-9áéíóúñ]+/gi, '-').replace(/^-|-$/g, '')
      : 'general';
    const filename = `tava-reporte-${scopeName}.${format}`;
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
    this.kpisLoading.set(true);
    const params = this.selectedReportEventId ? { event_id: this.selectedReportEventId } : undefined;
    this.api.get<Kpis>('/dashboard/kpis', params).pipe(
      finalize(() => this.kpisLoading.set(false))
    ).subscribe({
      next: (k) => this.kpis.set(k),
      error: () => this.notify.error('Métricas', 'No se pudo cargar el reporte seleccionado'),
    });
  }

  onReportScopeChange(): void {
    this.loadKpis();
  }

  reportTitle(): string {
    return this.kpis()?.event_name || 'Todos los eventos';
  }

  reportSubtitle(): string {
    const report = this.kpis();
    if (!report?.event_name) {
      return 'Vista consolidada de toda la operación TAVA';
    }
    const selected = this.adminEvents().find((event) => event.id === report.event_id);
    return `${selected?.category || 'Evento'} · ${report.event_date || selected?.event_date || ''} · ${selected?.city || ''}`;
  }

  loadAdminEvents(): void {
    this.adminEventsLoading.set(true);
    this.adminEventsError.set(null);
    this.api
      .get<TavaEvent[]>('/events/admin/all')
      .pipe(
        timeout(ADMIN_EVENTS_TIMEOUT_MS),
        catchError(() => {
          this.adminEventsError.set('No se pudieron cargar los eventos. Reintenta en unos segundos.');
          return of(null);
        }),
        finalize(() => this.adminEventsLoading.set(false))
      )
      .subscribe((events) => {
        if (events) this.adminEvents.set(events);
      });
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

  liveSeatingSeats(): SeatMapItem[] {
    return mergeSeatingPreview(this.seatingDraft, this.savedSeatingSeats);
  }

  seatingTicketTypeOptions(): SeatTicketTypeOption[] {
    return this.ticketTypesDraft
      .filter((t) => t.id)
      .map((t) => ({ id: t.id!, name: t.name }));
  }

  seatingTotalSeats(): number {
    return countLayoutSeats(this.seatingDraft);
  }

  seatingCapacityExceeded(): boolean {
    const cap = this.eventForm.capacity || 0;
    return cap > 0 && this.seatingDraft.enabled && this.seatingTotalSeats() > cap;
  }

  seatingTicketTypeOverflow(): string | null {
    if (!this.seatingDraft.enabled) return null;
    const counts = countSeatsByTicketType(this.seatingDraft);
    for (const tt of this.ticketTypesDraft) {
      if (!tt.id) continue;
      const assigned = counts[tt.id] ?? 0;
      if (assigned > (tt.quantity_available || 0)) {
        return `«${tt.name}»: ${assigned} sillas asignadas pero solo ${tt.quantity_available} cupos en boletería.`;
      }
    }
    return null;
  }

  addSeatingBlock(): void {
    const cap = this.eventForm.capacity || 0;
    const next = newSeatingBlock(this.seatingDraft.blocks.length);
    if (cap > 0 && this.seatingTotalSeats() + next.rows * next.cols > cap) {
      this.notify.warning(
        'Aforo',
        `No puedes agregar otro bloque: superarías el aforo de ${cap} sillas.`
      );
      return;
    }
    this.seatingDraft = {
      ...this.seatingDraft,
      blocks: [...this.seatingDraft.blocks, next],
    };
  }

  removeSeatingBlock(index: number): void {
    if (this.seatingDraft.blocks.length <= 1) {
      this.notify.warning('Silletería', 'Debe quedar al menos un bloque.');
      return;
    }
    const blocks = [...this.seatingDraft.blocks];
    blocks.splice(index, 1);
    this.seatingDraft = { ...this.seatingDraft, blocks };
  }

  onBlockTicketTypeChange(blockId: string, typeId: string): void {
    this.seatingDraft = applyBlockTicketType(this.seatingDraft, blockId, typeId || null);
  }

  onSeatTicketTypeAssign(event: {
    blockId: string;
    row: string;
    col: string;
    ticketTypeId: string | null;
  }): void {
    this.seatingDraft = applySeatTicketType(
      this.seatingDraft,
      event.blockId,
      event.row,
      event.col,
      event.ticketTypeId
    );
  }

  onBlockRowLabelsInput(block: { row_labels?: string[]; rows: number }, value: string): void {
    const labels = value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    block.row_labels = labels.length ? labels : undefined;
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
  }

  removeTicketType(index: number): void {
    this.ticketTypesDraft.splice(index, 1);
    this.ticketTypesTouched = true;
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
    this.duplicateGalleryDraft = [];
    this.theatrical = {
      sale_mode: 'system',
      whatsapp_number: '',
      whatsapp_message: '',
    };
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
    this.attendeesData.set(null);
    this.attendeesQuery.set('');
    this.broadcastSubject = '';
    this.broadcastMessage = '';
    this.seatingDraft = structuredClone(DEFAULT_SEATING);
    this.savedSeatingSeats = [];
    this.adminSeatPreviewSelected = [];
    this.seatingAssignTicketTypeId = null;
  }

  loadAttendees(eventId: string): void {
    this.attendeesLoading.set(true);
    this.attendeesQuery.set('');
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

  isFirstOrderRow(attendee: AttendeeItem): boolean {
    return this.filteredAttendees().find((item) => item.order_id === attendee.order_id)?.ticket_id === attendee.ticket_id;
  }

  resendOrderEmail(attendee: AttendeeItem): void {
    const destination = attendee.recipient_email || 'el correo original';
    this.notify.confirm(
      'Reenviar boletas',
      `Se reenviará el PDF de toda la orden a ${destination}. ¿Continuar?`,
      () => {
        this.notify.loadingTheatrical('Reenviando boletas', 'admin');
        this.api
          .post<{ email_sent: boolean; message: string }>(
            `/tickets/admin/orders/${attendee.order_id}/resend-email`,
            {}
          )
          .subscribe({
            next: (res) => {
              this.notify.hide();
              this.notify.success('Boletas', res.message || `Correo reenviado a ${destination}.`);
            },
            error: (err) => {
              this.notify.hide();
              this.notify.error(
                'Boletas',
                err.error?.detail ?? 'El proveedor no confirmó el reenvío.'
              );
            },
          });
      }
    );
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

  private showReviewNotification(n: ReviewNotification): void {
    if (n.notified) {
      this.notify.success('Revisión', 'Se notificó al administrador global por correo.');
      return;
    }
    if (n.reason === 'correo_no_configurado') {
      this.notify.warning('Revisión', 'El evento quedó pendiente, pero el correo no está configurado.');
      return;
    }
    if (!n.notified) {
      this.notify.warning('Revisión', 'El evento quedó pendiente, pero no se pudo enviar el aviso por correo.');
    }
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

  loadEventSeating(eventId: string): void {
    this.api.get<{ seats: SeatMapItem[] }>(`/events/${eventId}/seating`).subscribe({
      next: (res) => {
        this.savedSeatingSeats = res.seats ?? [];
      },
      error: () => {
        this.savedSeatingSeats = [];
      },
    });
  }

  saveEventSeating(): void {
    const id = this.editingId();
    if (!id) return;
    if (this.seatingCapacityExceeded()) {
      this.notify.warning(
        'Aforo',
        `El mapa tiene ${this.seatingTotalSeats()} sillas pero el aforo es ${this.eventForm.capacity}.`
      );
      return;
    }
    const overflow = this.seatingTicketTypeOverflow();
    if (overflow) {
      this.notify.warning('Categorías', overflow);
      return;
    }
    this.notify.loadingTheatrical('Generando silletería', 'admin');
    this.api.put<{ seats_created?: number }>(`/events/${id}/seating`, { seating: this.seatingDraft }).subscribe({
      next: (res) => {
        this.notify.hide();
        this.loadEventSeating(id);
        this.adminSeatPreviewSelected = [];
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
    this.duplicateGalleryDraft = [];
    this.editingId.set(ev.id);
    this.ticketTypesDraft = [];
    this.ticketTypesTouched = false;
    this.adminSeatPreviewSelected = [];
    this.api.get<TavaEventDetail>(`/events/${ev.id}/manage`).subscribe({
      next: (detail) => {
        this.ticketTypesDraft = (detail.ticket_types ?? []).map((t) => ({
          id: t.id,
          name: t.name,
          kind: t.kind as TicketKind,
          price: Number(t.price),
          quantity_available: t.quantity_available,
          benefits: t.benefits ?? '',
        }));
        this.seatingAssignTicketTypeId = this.ticketTypesDraft.find((t) => t.id)?.id ?? null;
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
    this.theatrical.sale_mode = this.theatrical.sale_mode ?? 'system';
    this.theatrical.whatsapp_number = this.theatrical.whatsapp_number ?? '';
    this.theatrical.whatsapp_message = this.theatrical.whatsapp_message ?? '';
    const td = ev.theatrical_details;
    if (td?.cast_members?.length) {
      this.castMembers = td.cast_members.map((m) => ({ ...m }));
    } else if (td?.cast?.length) {
      this.castMembers = td.cast.map((name) => ({ name, photo_url: '', role: '' }));
    } else {
      this.castMembers = [{ name: '', photo_url: '', role: '' }];
    }
    const seating = ev.theatrical_details?.seating;
    this.seatingDraft = seating
      ? {
          ...DEFAULT_SEATING,
          ...seating,
          blocks: seating.blocks?.length ? seating.blocks : DEFAULT_SEATING.blocks,
          seat_ticket_types: seating.seat_ticket_types ?? {},
        }
      : structuredClone(DEFAULT_SEATING);
    this.loadEventSeating(ev.id);
    this.loadAttendees(ev.id);
  }

  duplicateEvent(ev: TavaEvent): void {
    this.notify.loadingTheatrical('Duplicando evento', 'admin');
    this.api.get<TavaEventDetail>(`/events/${ev.id}/manage`).subscribe({
      next: (detail) => {
        this.notify.hide();
        this.editingId.set(null);
        this.eventForm = {
          name: detail.name,
          description: detail.description,
          category: detail.category,
          event_date: '',
          event_time: detail.event_time?.slice(0, 5) ?? '19:30',
          city: detail.city,
          address: detail.address,
          capacity: detail.capacity,
          status: 'borrador',
          main_image_url: detail.main_image_url ?? '',
          trailer_url: detail.trailer_url ?? '',
        };
        this.theatrical = {
          ...(detail.theatrical_details ?? {}),
          sale_mode: detail.theatrical_details?.sale_mode ?? 'system',
          whatsapp_number: detail.theatrical_details?.whatsapp_number ?? '',
          whatsapp_message: detail.theatrical_details?.whatsapp_message ?? '',
        };
        const td = detail.theatrical_details;
        if (td?.cast_members?.length) {
          this.castMembers = td.cast_members.map((m) => ({ ...m }));
        } else if (td?.cast?.length) {
          this.castMembers = td.cast.map((name) => ({ name, photo_url: '', role: '' }));
        } else {
          this.castMembers = [{ name: '', photo_url: '', role: '' }];
        }
        this.ticketTypesDraft = (detail.ticket_types ?? []).map((t) => ({
          name: t.name,
          kind: t.kind as TicketKind,
          price: Number(t.price),
          quantity_available: t.quantity_available,
          benefits: t.benefits ?? '',
        }));
        this.ticketTypesTouched = true;
        this.duplicateGalleryDraft = [...(detail.gallery ?? [])];
        this.attendeesData.set(null);
        this.broadcastSubject = '';
        this.broadcastMessage = '';
        this.notify.success('Eventos', 'Copia lista. Cambia la fecha y guarda el nuevo evento.');
        document.querySelector('.admin-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      },
      error: () => {
        this.notify.hide();
        this.notify.error('Eventos', 'No se pudo duplicar el evento');
      },
    });
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
        sale_mode: this.theatrical.sale_mode ?? 'system',
        whatsapp_number: this.theatrical.whatsapp_number?.trim() || null,
        whatsapp_message: this.theatrical.whatsapp_message?.trim() || null,
        cast: members.map((m) => m.name),
        cast_members: members,
        seating: {
          enabled: false,
          stage_label: 'Escenario',
          blocks: [],
          seat_ticket_types: {},
        },
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
        const reviewNotification = id
          ? (saved as EventUpdateResponse).review_notification
          : undefined;
        const finish = () => {
          this.notify.hide();
          this.notify.success('Eventos', id ? 'Evento actualizado' : 'Evento creado');
          if (attendeeNotification) {
            this.showAttendeeNotification(attendeeNotification);
          }
          if (reviewNotification) {
            this.showReviewNotification(reviewNotification);
          }
          this.resetEventForm();
          this.loadAdminEvents();
        };
        const finishAfterGallery = () => {
          if (id || !this.duplicateGalleryDraft.length) {
            finish();
            return;
          }
          this.copyDuplicateGallery(eventId, finish);
        };
        const shouldSync = id ? this.ticketTypesTouched : this.ticketTypesDraft.length > 0;
        if (shouldSync) {
          this.syncTicketTypes(eventId, finishAfterGallery);
        } else {
          finishAfterGallery();
        }
      },
      error: (err) => {
        this.notify.hide();
        const detail = err?.error?.detail ?? err?.error?.message;
        this.notify.error('Eventos', typeof detail === 'string' ? detail : 'No se pudo guardar el evento');
      },
    });
  }

  private copyDuplicateGallery(eventId: string, onDone: () => void): void {
    let pending = this.duplicateGalleryDraft.length;
    let failed = false;
    const done = () => {
      pending -= 1;
      if (pending === 0) {
        if (failed) {
          this.notify.warning('Galeria', 'Evento creado, pero no se pudo copiar toda la galeria.');
        }
        onDone();
      }
    };
    for (const item of this.duplicateGalleryDraft) {
      this.api
        .post(`/events/${eventId}/media`, {
          media_type: item.media_type,
          url: item.url,
          sort_order: item.sort_order ?? 0,
        })
        .subscribe({
          next: () => done(),
          error: () => {
            failed = true;
            done();
          },
        });
    }
  }

  private syncTicketTypes(eventId: string, onDone: () => void): void {
    const ticketTypes = this.ticketTypesDraft
      .map((t) => ({
        id: t.id ?? null,
        name: t.name.trim(),
        kind: t.kind,
        price: Number(t.price) || 0,
        quantity_available: Number(t.quantity_available) || 0,
        benefits: t.benefits?.trim() || null,
      }))
      .filter((t) => t.id || t.name || t.price > 0 || t.quantity_available > 0 || t.benefits);
    if (ticketTypes.some((t) => !t.name)) {
      this.notify.hide();
      this.notify.warning('Boletería', 'Cada tipo de boleta debe tener nombre.');
      return;
    }
    const payload = {
      ticket_types: ticketTypes,
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

  saveAppearance(): void {
    this.notify.loadingTheatrical('Ajustando el telón', 'upload');
    this.site.updateAppearance(this.appearanceForm).subscribe({
      next: (a: SiteAppearance) => {
        this.notify.hide();
        this.site.appearance.set(a);
        this.notify.success('Apariencia', 'Video del loader actualizado');
      },
      error: () => {
        this.notify.hide();
        this.notify.error('Apariencia', 'No se pudo guardar');
      },
    });
  }
}
