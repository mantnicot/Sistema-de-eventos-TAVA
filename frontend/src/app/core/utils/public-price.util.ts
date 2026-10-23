/** Igual que el backend: cubre la tarifa de Wompi y redondea hacia arriba a centenas. */

export interface CheckoutFees {
  fee_percent: number;
  fee_fixed_cop: number;
  fee_iva: number;
  rounding_step: number;
}

export const DEFAULT_CHECKOUT_FEES: CheckoutFees = {
  fee_percent: 0.0265,
  fee_fixed_cop: 700,
  fee_iva: 0.19,
  rounding_step: 100,
};

export function publicCharge(base: number, fees: CheckoutFees = DEFAULT_CHECKOUT_FEES): number {
  const amount = Number(base) || 0;
  if (amount <= 0) return 0;
  const rate = fees.fee_percent * (1 + fees.fee_iva);
  const fixedGross = fees.fee_fixed_cop * (1 + fees.fee_iva);
  const raw = rate >= 1 ? amount + fixedGross : (amount + fixedGross) / (1 - rate);
  const step = fees.rounding_step || 100;
  return Math.ceil(raw / step) * step;
}
