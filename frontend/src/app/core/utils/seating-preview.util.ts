import {
  colLabelsForBlock,
  resolveSeatTicketTypeId,
  rowLabelsForBlock,
  SeatingConfig,
  SeatMapItem,
} from '../models/seating.model';

/** Genera sillas disponibles a partir de la configuración (vista previa admin). */
export function buildSeatsFromConfig(config: SeatingConfig): SeatMapItem[] {
  if (!config.enabled) return [];
  const seats: SeatMapItem[] = [];
  for (const block of config.blocks) {
    for (const row of rowLabelsForBlock(block)) {
      for (const col of colLabelsForBlock(block)) {
        seats.push({
          id: `preview-${block.id}-${row}-${col}`,
          block_id: block.id,
          row,
          col,
          label: `${block.name} · Fila ${row} · Asiento ${col}`,
          status: 'disponible',
          ticket_type_id: resolveSeatTicketTypeId(config, block.id, row, col),
        });
      }
    }
  }
  return seats;
}

/** Combina layout nuevo con sillas ya vendidas del servidor. */
export function mergeSeatingPreview(config: SeatingConfig, saved: SeatMapItem[]): SeatMapItem[] {
  const preview = buildSeatsFromConfig(config);
  if (!saved.length) return preview;
  const savedByPos = new Map(saved.map((s) => [`${s.block_id}|${s.row}|${s.col}`, s]));
  return preview.map((p) => {
    const existing = savedByPos.get(`${p.block_id}|${p.row}|${p.col}`);
    if (!existing) return p;
    return {
      ...p,
      id: existing.id,
      status: existing.status,
      ticket_type_id: existing.ticket_type_id ?? p.ticket_type_id,
    };
  });
}

export function applySeatTicketType(
  config: SeatingConfig,
  blockId: string,
  row: string,
  col: string,
  ticketTypeId: string | null
): SeatingConfig {
  const key = `${blockId}|${row}|${col}`;
  const seat_ticket_types = { ...(config.seat_ticket_types ?? {}) };
  if (ticketTypeId) seat_ticket_types[key] = ticketTypeId;
  else delete seat_ticket_types[key];
  return { ...config, seat_ticket_types };
}

export function applyBlockTicketType(
  config: SeatingConfig,
  blockId: string,
  ticketTypeId: string | null
): SeatingConfig {
  const blocks = config.blocks.map((b) =>
    b.id === blockId ? { ...b, ticket_type_id: ticketTypeId || null } : b
  );
  const seat_ticket_types = { ...(config.seat_ticket_types ?? {}) };
  const block = blocks.find((b) => b.id === blockId);
  if (block) {
    for (const row of rowLabelsForBlock(block)) {
      for (const col of colLabelsForBlock(block)) {
        delete seat_ticket_types[`${blockId}|${row}|${col}`];
      }
    }
  }
  return { ...config, blocks, seat_ticket_types };
}
