export interface CastMember {
  name: string;
  photo_url?: string;
  role?: string;
}

import { SeatingConfig } from './seating.model';

export interface TheatricalDetails {
  synopsis?: string;
  cast?: string[];
  cast_members?: CastMember[];
  director?: string;
  duration_minutes?: number;
  age_rating?: string;
  language?: string;
  warnings?: string;
  credits?: string;
  seating?: SeatingConfig;
  sale_mode?: 'system' | 'whatsapp';
  whatsapp_number?: string;
  whatsapp_message?: string;
}

export interface TavaEvent {
  id: string;
  name: string;
  description: string;
  event_date: string;
  event_time: string;
  city: string;
  address: string;
  category: string;
  status: string;
  capacity: number;
  tickets_available?: number;
  main_image_url?: string;
  trailer_url?: string;
  theatrical_details?: TheatricalDetails;
  review_status?: 'pendiente' | 'aprobado' | 'rechazado';
  cartelera_visible?: boolean;
  organizer_id?: string;
  organizer_name?: string;
  rejection_reason?: string;
  commission_rate?: number | null;
  contract_version?: string | null;
  contract_accepted_at?: string | null;
  entry_unlocked?: boolean | null;
  pre_settlement_fee?: number | null;
  pre_settlement_confirmed_at?: string | null;
  pre_settlement_notified_at?: string | null;
  post_settlement_fee?: number | null;
  post_settlement_notified_at?: string | null;
}

export interface TavaEventDetail extends TavaEvent {
  gallery: { id: string; media_type: string; url: string; sort_order: number }[];
  ticket_types: {
    id: string;
    name: string;
    kind: string;
    price: number;
    quantity_available: number;
    benefits?: string;
  }[];
  seating_enabled?: boolean;
}
