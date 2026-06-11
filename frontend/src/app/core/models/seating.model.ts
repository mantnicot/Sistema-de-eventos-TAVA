export interface SeatingBlockConfig {
  id: string;
  name: string;
  rows: number;
  cols: number;
  row_labels?: string[];
  col_labels?: string[];
  /** Tipo de boleta por defecto para todo el bloque */
  ticket_type_id?: string | null;
}

export interface SeatingConfig {
  enabled: boolean;
  stage_label?: string;
  blocks: SeatingBlockConfig[];
  /** Asignación individual: clave "blockId|row|col" → ticket_type_id */
  seat_ticket_types?: Record<string, string>;
}

export interface SeatMapItem {
  id: string;
  block_id: string;
  row: string;
  col: string;
  label: string;
  status: 'disponible' | 'vendida' | 'bloqueada' | 'reservada';
  ticket_type_id?: string | null;
}

export interface SeatMapResponse {
  enabled: boolean;
  config: SeatingConfig | null;
  seats: SeatMapItem[];
}

export interface SeatTicketTypeOption {
  id: string;
  name: string;
}

export const SEAT_TYPE_COLORS = [
  '#4fc3f7',
  '#ffb74d',
  '#ce93d8',
  '#81c784',
  '#f06292',
  '#fff176',
  '#80cbc4',
  '#ff8a65',
];

export const DEFAULT_SEATING: SeatingConfig = {
  enabled: false,
  stage_label: 'Escenario',
  blocks: [
    { id: 'left', name: 'Bloque izquierdo', rows: 4, cols: 6 },
    { id: 'right', name: 'Bloque derecho', rows: 4, cols: 6 },
  ],
  seat_ticket_types: {},
};

export function seatPositionKey(blockId: string, row: string, col: string): string {
  return `${blockId}|${row}|${col}`;
}

export function rowLabelsForBlock(block: SeatingBlockConfig): string[] {
  if (block.row_labels?.length) return block.row_labels.slice(0, block.rows);
  return Array.from({ length: block.rows }, (_, i) =>
    i < 26 ? String.fromCharCode(65 + i) : String(i + 1)
  );
}

export function colLabelsForBlock(block: SeatingBlockConfig): string[] {
  if (block.col_labels?.length) return block.col_labels.slice(0, block.cols);
  return Array.from({ length: block.cols }, (_, i) => String(i + 1));
}

export function countLayoutSeats(config: SeatingConfig): number {
  if (!config.enabled) return 0;
  return config.blocks.reduce((sum, b) => sum + (b.rows || 0) * (b.cols || 0), 0);
}

export function resolveSeatTicketTypeId(
  config: SeatingConfig,
  blockId: string,
  row: string,
  col: string
): string | null {
  const key = seatPositionKey(blockId, row, col);
  const override = config.seat_ticket_types?.[key];
  if (override) return override;
  const block = config.blocks.find((b) => b.id === blockId);
  return block?.ticket_type_id ?? null;
}

export function countSeatsByTicketType(
  config: SeatingConfig
): Record<string, number> {
  const counts: Record<string, number> = {};
  if (!config.enabled) return counts;
  for (const block of config.blocks) {
    for (const row of rowLabelsForBlock(block)) {
      for (const col of colLabelsForBlock(block)) {
        const ttId = resolveSeatTicketTypeId(config, block.id, row, col);
        if (ttId) counts[ttId] = (counts[ttId] ?? 0) + 1;
      }
    }
  }
  return counts;
}

export function newSeatingBlock(index: number): SeatingBlockConfig {
  const id = `block-${Date.now()}-${index}`;
  return {
    id,
    name: `Bloque ${index + 1}`,
    rows: 4,
    cols: 6,
  };
}

export function ticketTypeColor(typeId: string | null | undefined, types: SeatTicketTypeOption[]): string | null {
  if (!typeId) return null;
  const idx = types.findIndex((t) => t.id === typeId);
  if (idx < 0) return SEAT_TYPE_COLORS[0];
  return SEAT_TYPE_COLORS[idx % SEAT_TYPE_COLORS.length];
}

export function ticketTypeName(typeId: string | null | undefined, types: SeatTicketTypeOption[]): string {
  if (!typeId) return 'Sin categoría';
  return types.find((t) => t.id === typeId)?.name ?? 'Boleta';
}
