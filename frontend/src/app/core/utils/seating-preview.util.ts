import { SeatingBlockConfig, SeatingConfig, SeatMapItem } from '../models/seating.model';

function rowLabels(block: SeatingBlockConfig): string[] {
  if (block.row_labels?.length) return block.row_labels.slice(0, block.rows);
  return Array.from({ length: block.rows }, (_, i) =>
    i < 26 ? String.fromCharCode(65 + i) : String(i + 1)
  );
}

function colLabels(block: SeatingBlockConfig): string[] {
  if (block.col_labels?.length) return block.col_labels.slice(0, block.cols);
  return Array.from({ length: block.cols }, (_, i) => String(i + 1));
}

/** Genera sillas disponibles a partir de la configuración (vista previa admin). */
export function buildSeatsFromConfig(config: SeatingConfig): SeatMapItem[] {
  if (!config.enabled) return [];
  const seats: SeatMapItem[] = [];
  for (const block of config.blocks) {
    for (const row of rowLabels(block)) {
      for (const col of colLabels(block)) {
        seats.push({
          id: `preview-${block.id}-${row}-${col}`,
          block_id: block.id,
          row,
          col,
          label: `${block.name} · Fila ${row} · Asiento ${col}`,
          status: 'disponible',
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
  const soldByPos = new Map(
    saved
      .filter((s) => s.status === 'vendida')
      .map((s) => [`${s.block_id}|${s.row}|${s.col}`, s])
  );
  return preview.map((p) => {
    const sold = soldByPos.get(`${p.block_id}|${p.row}|${p.col}`);
    if (sold) return { ...p, id: sold.id, status: 'vendida' };
    return p;
  });
}
