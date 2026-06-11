export interface PurchaseDraft {
  eventId: string;
  selectedTypeId: string | null;
  quantity: number;
  singleHolderMode: boolean;
  holderName: string;
  holderNames: string[];
  legalAccepted: boolean;
  selectedSeatIds: string[];
}

const KEY = 'tava_purchase_draft';

export function savePurchaseDraft(draft: PurchaseDraft): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(draft));
  } catch {
    /* private mode */
  }
}

export function readPurchaseDraft(eventId: string): PurchaseDraft | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw) as PurchaseDraft;
    return draft.eventId === eventId ? draft : null;
  } catch {
    return null;
  }
}

export function clearPurchaseDraft(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
