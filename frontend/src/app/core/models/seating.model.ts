export interface SeatingBlockConfig {
  id: string;
  name: string;
  rows: number;
  cols: number;
  row_labels?: string[];
  col_labels?: string[];
}

export interface SeatingConfig {
  enabled: boolean;
  stage_label?: string;
  blocks: SeatingBlockConfig[];
}

export interface SeatMapItem {
  id: string;
  block_id: string;
  row: string;
  col: string;
  label: string;
  status: 'disponible' | 'vendida' | 'bloqueada' | 'reservada';
}

export interface SeatMapResponse {
  enabled: boolean;
  config: SeatingConfig | null;
  seats: SeatMapItem[];
}

export const DEFAULT_SEATING: SeatingConfig = {
  enabled: false,
  stage_label: 'Escenario',
  blocks: [
    { id: 'left', name: 'Bloque izquierdo', rows: 4, cols: 6 },
    { id: 'right', name: 'Bloque derecho', rows: 4, cols: 6 },
  ],
};
