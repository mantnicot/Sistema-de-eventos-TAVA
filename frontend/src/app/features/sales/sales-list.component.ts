import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { matchesSearch } from '../../core/utils/list-search.util';
import { parseHttpError } from '../../core/utils/http-error.util';
import { TavaListSearchComponent } from '../../shared/components/tava-list-search/tava-list-search.component';

interface SaleItem {
  ticket_id: string;
  order_id: string;
  event_id: string;
  event_name: string;
  event_date: string;
  event_time: string;
  city: string;
  holder_name: string | null;
  buyer_name: string | null;
  buyer_email: string | null;
  ticket_type: string;
  price: number;
  platform_fee: number;
  organizer_net: number;
  ticket_code: string | null;
  claim_code: string | null;
  status: string;
  is_used: boolean;
  is_cancelled: boolean;
  channel: string;
  payment_provider: string | null;
  sold_at: string | null;
  pdf_url: string;
}

interface SalesEventOption {
  id: string;
  name: string;
}

interface SalesSummary {
  boletas: number;
  boletas_totales: number;
  personas: number;
  bruto: number;
  comision_plataforma: number;
  neto_organizador: number;
}

interface SalesResponse {
  fee_rate: number;
  items: SaleItem[];
  summary: SalesSummary;
  events: SalesEventOption[];
}

@Component({
  selector: 'app-sales-list',
  standalone: true,
  imports: [DecimalPipe, FormsModule, TavaListSearchComponent],
  templateUrl: './sales-list.component.html',
  styleUrl: './sales-list.component.scss',
})
export class SalesListComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(true);
  readonly items = signal<SaleItem[]>([]);
  readonly events = signal<SalesEventOption[]>([]);
  readonly summary = signal<SalesSummary>({
    boletas: 0,
    boletas_totales: 0,
    personas: 0,
    bruto: 0,
    comision_plataforma: 0,
    neto_organizador: 0,
  });
  readonly feeRate = signal(0.06);
  readonly query = signal('');
  readonly eventFilter = signal('');
  readonly statusFilter = signal<'all' | 'valida' | 'usada' | 'cancelada'>('all');
  readonly channelFilter = signal<'all' | 'online' | 'taquilla' | 'manual' | 'otro'>('all');

  readonly filteredItems = computed(() => {
    const q = this.query();
    const status = this.statusFilter();
    const channel = this.channelFilter();
    return this.items().filter((item) => {
      if (status !== 'all' && item.status !== status) return false;
      if (channel !== 'all' && item.channel !== channel) return false;
      return matchesSearch(
        q,
        item.event_name,
        item.holder_name,
        item.buyer_name,
        item.buyer_email,
        item.ticket_code,
        item.claim_code,
        item.ticket_type,
        item.city,
        item.channel,
        item.status
      );
    });
  });

  readonly filteredSummary = computed(() => {
    const rows = this.filteredItems().filter((item) => !item.is_cancelled);
    const bruto = rows.reduce((sum, item) => sum + (item.price || 0), 0);
    const fee = rows.reduce((sum, item) => sum + (item.platform_fee || 0), 0);
    const people = new Set(
      rows.map((item) => (item.buyer_email || item.buyer_name || item.holder_name || item.ticket_id).toLowerCase())
    );
    return {
      boletas: rows.length,
      personas: people.size,
      bruto,
      comision_plataforma: fee,
      neto_organizador: bruto - fee,
    };
  });

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    const eventId = this.eventFilter();
    const params = eventId ? { event_id: eventId } : undefined;
    this.api.get<SalesResponse>('/tickets/sales', params).subscribe({
      next: (res) => {
        this.items.set(res.items ?? []);
        if (!eventId) {
          this.events.set(res.events ?? []);
        } else if (!(res.events ?? []).length && this.events().length === 0) {
          this.events.set(res.events ?? []);
        } else if ((res.events ?? []).length) {
          const known = new Map(this.events().map((e) => [e.id, e.name]));
          for (const ev of res.events) known.set(ev.id, ev.name);
          this.events.set([...known.entries()].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name)));
        }
        this.summary.set(
          res.summary ?? {
            boletas: 0,
            boletas_totales: 0,
            personas: 0,
            bruto: 0,
            comision_plataforma: 0,
            neto_organizador: 0,
          }
        );
        this.feeRate.set(res.fee_rate ?? 0.06);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.items.set([]);
        this.notify.showHttpError(parseHttpError(err, 'ventas'));
      },
    });
  }

  onEventFilter(value: string): void {
    this.eventFilter.set(value || '');
    this.reload();
  }

  onStatusFilter(value: string): void {
    this.statusFilter.set((value as 'all' | 'valida' | 'usada' | 'cancelada') || 'all');
  }

  onChannelFilter(value: string): void {
    this.channelFilter.set((value as 'all' | 'online' | 'taquilla' | 'manual' | 'otro') || 'all');
  }

  channelLabel(channel: string): string {
    switch (channel) {
      case 'online':
        return 'Online';
      case 'taquilla':
        return 'Taquilla';
      case 'manual':
        return 'Manual';
      default:
        return 'Otro';
    }
  }

  statusLabel(status: string): string {
    switch (status) {
      case 'usada':
        return 'Usada';
      case 'cancelada':
        return 'Cancelada';
      default:
        return 'Válida';
    }
  }

  formatSoldAt(value: string | null): string {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('es-CO', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  }

  downloadPdf(item: SaleItem): void {
    this.api.downloadBlob(item.pdf_url).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `boleta-${item.ticket_code || item.ticket_id}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      },
      error: () => this.notify.error('PDF', 'No se pudo descargar el PDF'),
    });
  }
}
