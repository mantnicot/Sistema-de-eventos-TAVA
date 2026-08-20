import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { TavaEvent } from '../../core/models/event.model';
import { parseHttpError } from '../../core/utils/http-error.util';

export type StaffRole = 'general' | 'seller' | 'validator' | 'admin';

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: StaffRole;
  email_verified: boolean;
  is_active: boolean;
  validator_event_ids?: string[];
  seller_event_ids?: string[];
}

interface RoleOption {
  value: StaffRole;
  label: string;
  hint: string;
  icon: string;
}

@Component({
  selector: 'tava-admin-users-panel',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './admin-users-panel.component.html',
  styleUrl: './admin-users-panel.component.scss',
})
export class AdminUsersPanelComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  readonly roles: RoleOption[] = [
    { value: 'general', label: 'Público', hint: 'Compra boletas y usa su perfil', icon: 'P' },
    { value: 'seller', label: 'Vendedor', hint: 'Vende en las obras asignadas', icon: 'V' },
    { value: 'validator', label: 'Validador', hint: 'Controla el ingreso con QR', icon: 'Q' },
    { value: 'admin', label: 'Admin', hint: 'Acceso total al panel TAVA', icon: 'A' },
  ];

  readonly users = signal<AdminUser[]>([]);
  readonly events = signal<TavaEvent[]>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly selectedId = signal<string | null>(null);
  readonly query = signal('');
  readonly roleFilter = signal<'all' | StaffRole>('all');
  readonly eventQuery = signal('');
  readonly draftRole = signal<StaffRole>('general');
  readonly draftActive = signal(true);
  readonly draftEventIds = signal<string[]>([]);

  readonly selected = computed(() => this.users().find((u) => u.id === this.selectedId()) ?? null);

  readonly filteredUsers = computed(() => {
    const q = this.query().trim().toLowerCase();
    const role = this.roleFilter();
    return this.users().filter((u) => {
      if (role !== 'all' && u.role !== role) return false;
      if (!q) return true;
      return u.full_name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
    });
  });

  readonly visibleEvents = computed(() => {
    const q = this.eventQuery().trim().toLowerCase();
    const list = this.events();
    if (!q) return list;
    return list.filter(
      (ev) =>
        ev.name.toLowerCase().includes(q) ||
        ev.city.toLowerCase().includes(q) ||
        ev.status.toLowerCase().includes(q)
    );
  });

  readonly counts = computed(() => {
    const list = this.users();
    return {
      total: list.length,
      admin: list.filter((u) => u.role === 'admin').length,
      seller: list.filter((u) => u.role === 'seller').length,
      validator: list.filter((u) => u.role === 'validator').length,
    };
  });

  readonly needsEvents = computed(() => {
    const role = this.draftRole();
    return role === 'seller' || role === 'validator';
  });

  readonly dirty = computed(() => {
    const user = this.selected();
    if (!user) return false;
    const original = this.eventIdsFor(user).slice().sort().join(',');
    const draft = this.draftEventIds().slice().sort().join(',');
    return user.role !== this.draftRole() || user.is_active !== this.draftActive() || original !== draft;
  });

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    forkJoin({
      users: this.api.get<AdminUser[]>('/users', { limit: 200 }),
      events: this.api.get<TavaEvent[]>('/events/admin/all', { limit: 200 }),
    }).subscribe({
      next: ({ users, events }) => {
        this.users.set(users ?? []);
        this.events.set(events ?? []);
        this.loading.set(false);
        const current = this.selectedId();
        if (current && !users.some((u) => u.id === current)) {
          this.selectedId.set(null);
        } else if (current) {
          const fresh = users.find((u) => u.id === current);
          if (fresh) this.applyUserToDraft(fresh);
        }
      },
      error: (err) => {
        this.loading.set(false);
        this.notify.showHttpError(parseHttpError(err, 'usuarios'));
      },
    });
  }

  selectUser(user: AdminUser): void {
    this.selectedId.set(user.id);
    this.eventQuery.set('');
    this.applyUserToDraft(user);
  }

  closeEditor(): void {
    this.selectedId.set(null);
  }

  onQuery(value: string): void {
    this.query.set(value ?? '');
  }

  onRoleFilter(value: string): void {
    this.roleFilter.set((value as 'all' | StaffRole) || 'all');
  }

  onEventQuery(value: string): void {
    this.eventQuery.set(value ?? '');
  }

  onActiveChange(value: boolean): void {
    this.draftActive.set(!!value);
  }

  setDraftRole(role: StaffRole): void {
    if (this.isCurrentUser(this.selected()) && role !== 'admin') {
      this.notify.warning('Tu cuenta', 'No puedes quitarte el rol de administrador.');
      return;
    }
    this.draftRole.set(role);
  }

  toggleEvent(eventId: string): void {
    const current = this.draftEventIds();
    this.draftEventIds.set(
      current.includes(eventId) ? current.filter((id) => id !== eventId) : [...current, eventId]
    );
  }

  isEventSelected(eventId: string): boolean {
    return this.draftEventIds().includes(eventId);
  }

  selectAllVisibleEvents(): void {
    const ids = new Set(this.draftEventIds());
    for (const ev of this.visibleEvents()) ids.add(ev.id);
    this.draftEventIds.set([...ids]);
  }

  clearEvents(): void {
    this.draftEventIds.set([]);
  }

  roleLabel(role: StaffRole): string {
    return this.roles.find((r) => r.value === role)?.label ?? role;
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  eventCount(user: AdminUser): number {
    return this.eventIdsFor(user).length;
  }

  isCurrentUser(user: AdminUser | null): boolean {
    return !!user && user.id === this.auth.user()?.id;
  }

  eventSummary(user: AdminUser): string {
    if (user.role === 'admin') return 'Todas las obras';
    if (user.role === 'general') return 'Sin acceso de personal';
    const n = this.eventCount(user);
    if (!n) return 'Sin obras asignadas';
    return n === 1 ? '1 obra asignada' : `${n} obras asignadas`;
  }

  save(): void {
    const user = this.selected();
    if (!user || !this.dirty()) return;
    this.saving.set(true);
    this.notify.loadingTheatrical('Guardando permisos', 'admin');
    this.api
      .patch<AdminUser>(`/users/${user.id}/permissions`, {
        role: this.draftRole(),
        is_active: this.draftActive(),
        event_ids: this.needsEvents() ? this.draftEventIds() : [],
      })
      .subscribe({
        next: (updated) => {
          this.saving.set(false);
          this.notify.hide();
          this.users.set(this.users().map((u) => (u.id === updated.id ? { ...u, ...updated } : u)));
          this.applyUserToDraft(updated);
          this.notify.success('Permisos', `Listo: ${updated.full_name} quedó como ${this.roleLabel(updated.role).toLowerCase()}.`);
        },
        error: (err) => {
          this.saving.set(false);
          this.notify.hide();
          this.notify.showHttpError(parseHttpError(err, 'permisos'));
        },
      });
  }

  deleteSelected(): void {
    const user = this.selected();
    if (!user) return;
    if (this.isCurrentUser(user)) {
      this.notify.warning('Alto en escena', 'No puedes eliminar tu propia cuenta.');
      return;
    }
    this.notify.confirm('Eliminar usuario', `¿Eliminar a ${user.full_name}? Esta acción no se deshace.`, () => {
      this.notify.loadingTheatrical('Fuera de escena', 'delete');
      this.api.delete(`/users/${user.id}`).subscribe({
        next: () => {
          this.notify.hide();
          this.users.set(this.users().filter((u) => u.id !== user.id));
          this.selectedId.set(null);
          this.notify.success('Usuarios', 'Usuario eliminado');
        },
        error: (err) => {
          this.notify.hide();
          this.notify.showHttpError(parseHttpError(err, 'eliminar usuario'));
        },
      });
    });
  }

  private applyUserToDraft(user: AdminUser): void {
    this.draftRole.set(user.role);
    this.draftActive.set(user.is_active);
    this.draftEventIds.set(this.eventIdsFor(user));
  }

  private eventIdsFor(user: AdminUser): string[] {
    const seller = user.seller_event_ids ?? [];
    const validator = user.validator_event_ids ?? [];
    if (user.role === 'seller') return [...new Set([...seller, ...validator])];
    if (user.role === 'validator') return [...new Set([...validator, ...seller])];
    return [];
  }
}
