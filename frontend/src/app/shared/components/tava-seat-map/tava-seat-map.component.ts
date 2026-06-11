import { Component, EventEmitter, Input, Output } from '@angular/core';
import {
  resolveSeatTicketTypeId,
  SeatMapItem,
  SeatingBlockConfig,
  SeatingConfig,
  SeatTicketTypeOption,
  ticketTypeColor,
  ticketTypeName,
} from '../../../core/models/seating.model';

export type SeatMapMode = 'purchase' | 'assign' | 'preview';

@Component({
  selector: 'tava-seat-map',
  standalone: true,
  templateUrl: './tava-seat-map.component.html',
  styleUrl: './tava-seat-map.component.scss',
})
export class TavaSeatMapComponent {
  @Input({ required: true }) config!: SeatingConfig;
  @Input({ required: true }) seats: SeatMapItem[] = [];
  @Input() selectedIds: string[] = [];
  @Input() readonly = false;
  @Input() mode: SeatMapMode = 'purchase';
  @Input() ticketTypes: SeatTicketTypeOption[] = [];
  @Input() activeTicketTypeId: string | null = null;
  @Input() allowedTicketTypeId: string | null = null;
  @Output() selectedIdsChange = new EventEmitter<string[]>();
  @Output() seatTicketTypeChange = new EventEmitter<{
    blockId: string;
    row: string;
    col: string;
    ticketTypeId: string | null;
  }>();

  ticketTypeColor = ticketTypeColor;

  seatFor(blockId: string, row: string, col: string): SeatMapItem | undefined {
    return this.seats.find((s) => s.block_id === blockId && s.row === row && s.col === col);
  }

  seatAt(block: SeatingBlockConfig, row: string, col: string): SeatMapItem | undefined {
    const existing = this.seatFor(block.id, row, col);
    if (existing) return existing;
    if (!this.config.enabled) return undefined;
    return {
      id: `preview-${block.id}-${row}-${col}`,
      block_id: block.id,
      row,
      col,
      label: `${block.name} · Fila ${row} · Asiento ${col}`,
      status: 'disponible',
      ticket_type_id: resolveSeatTicketTypeId(this.config, block.id, row, col),
    };
  }

  rowLabels(block: SeatingBlockConfig): string[] {
    if (block.row_labels?.length) return block.row_labels.slice(0, block.rows);
    return Array.from({ length: block.rows }, (_, i) =>
      i < 26 ? String.fromCharCode(65 + i) : String(i + 1)
    );
  }

  colLabels(block: SeatingBlockConfig): string[] {
    if (block.col_labels?.length) return block.col_labels.slice(0, block.cols);
    return Array.from({ length: block.cols }, (_, i) => String(i + 1));
  }

  seatTicketType(seat: SeatMapItem | undefined): string | null {
    if (!seat) return null;
    if (seat.ticket_type_id) return seat.ticket_type_id;
    return resolveSeatTicketTypeId(this.config, seat.block_id, seat.row, seat.col);
  }

  seatTypeColor(seat: SeatMapItem | undefined): string | null {
    return ticketTypeColor(this.seatTicketType(seat), this.ticketTypes);
  }

  seatClass(seat: SeatMapItem | undefined): string {
    if (!seat) return 'seat seat--empty';
    const selected = this.selectedIds.includes(seat.id);
    if (selected) return 'seat seat--selected';
    if (seat.status === 'vendida') return 'seat seat--sold';
    if (seat.status === 'bloqueada') return 'seat seat--blocked';
    if (seat.status === 'reservada') return 'seat seat--reserved';
    if (this.mode === 'purchase' && !this.seatSelectable(seat)) return 'seat seat--restricted';
    return 'seat seat--free';
  }

  seatSelectable(seat: SeatMapItem): boolean {
    if (seat.status !== 'disponible') return false;
    if (this.mode !== 'purchase' || !this.allowedTicketTypeId) return true;
    const tt = this.seatTicketType(seat);
    return tt === this.allowedTicketTypeId;
  }

  seatDisabled(seat: SeatMapItem | undefined): boolean {
    if (this.readonly || !seat) return true;
    if (this.mode === 'assign') {
      return seat.status === 'vendida';
    }
    return !this.seatSelectable(seat);
  }

  toggle(seat: SeatMapItem | undefined): void {
    if (!seat || this.seatDisabled(seat)) return;

    if (this.mode === 'assign') {
      const current = this.seatTicketType(seat);
      const next =
        this.activeTicketTypeId && current === this.activeTicketTypeId
          ? null
          : this.activeTicketTypeId;
      this.seatTicketTypeChange.emit({
        blockId: seat.block_id,
        row: seat.row,
        col: seat.col,
        ticketTypeId: next,
      });
      return;
    }

    const set = new Set(this.selectedIds);
    if (set.has(seat.id)) set.delete(seat.id);
    else set.add(seat.id);
    this.selectedIdsChange.emit([...set]);
  }

  ariaLabel(seat: SeatMapItem | undefined): string {
    if (!seat) return 'Sin silla';
    const typeLabel = ticketTypeName(this.seatTicketType(seat), this.ticketTypes);
    if (seat.status === 'vendida') return `${seat.label}, ocupada`;
    if (this.selectedIds.includes(seat.id)) return `${seat.label}, seleccionada, ${typeLabel}`;
    if (!this.seatSelectable(seat)) return `${seat.label}, no disponible para este tipo de boleta`;
    return `${seat.label}, disponible, ${typeLabel}`;
  }

  legendTypes(): SeatTicketTypeOption[] {
    if (!this.ticketTypes.length) return [];
    const used = new Set<string>();
    for (const seat of this.seats) {
      const tt = this.seatTicketType(seat);
      if (tt) used.add(tt);
    }
    if (!used.size && this.mode === 'assign') return this.ticketTypes;
    return this.ticketTypes.filter((t) => used.has(t.id));
  }
}
