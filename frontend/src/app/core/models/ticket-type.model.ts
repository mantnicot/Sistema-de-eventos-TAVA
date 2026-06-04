export type TicketKind =
  | 'individual'
  | 'grupal'
  | 'vip'
  | 'promocional'
  | 'cortesia';

export interface TicketTypeDraft {
  id?: string;
  name: string;
  kind: TicketKind;
  price: number;
  quantity_available: number;
  benefits?: string;
}

export interface TicketTypePublic {
  id: string;
  name: string;
  kind: TicketKind;
  price: number;
  quantity_available: number;
  benefits?: string;
}
