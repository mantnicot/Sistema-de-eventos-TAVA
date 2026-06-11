import { Component, EventEmitter, Input, Output } from '@angular/core';
import { SeatMapItem, SeatingBlockConfig, SeatingConfig } from '../../../core/models/seating.model';

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
  @Output() selectedIdsChange = new EventEmitter<string[]>();

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

  seatClass(seat: SeatMapItem | undefined): string {
    if (!seat) return 'seat seat--empty';
    const selected = this.selectedIds.includes(seat.id);
    if (selected) return 'seat seat--selected';
    if (seat.status === 'vendida') return 'seat seat--sold';
    if (seat.status === 'bloqueada') return 'seat seat--blocked';
    if (seat.status === 'reservada') return 'seat seat--reserved';
    return 'seat seat--free';
  }

  toggle(seat: SeatMapItem | undefined): void {
    if (this.readonly || !seat || seat.status !== 'disponible') return;
    const set = new Set(this.selectedIds);
    if (set.has(seat.id)) set.delete(seat.id);
    else set.add(seat.id);
    this.selectedIdsChange.emit([...set]);
  }

  ariaLabel(seat: SeatMapItem | undefined): string {
    if (!seat) return 'Sin silla';
    if (seat.status === 'vendida') return `${seat.label}, ocupada`;
    if (this.selectedIds.includes(seat.id)) return `${seat.label}, seleccionada`;
    return `${seat.label}, disponible`;
  }
}
