"""Precio al público: cubre la comisión de Wompi y redondea hacia arriba a centenas."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

DEFAULT_FEE_PERCENT = Decimal("0.0265")
DEFAULT_FEE_FIXED = Decimal("700")
DEFAULT_FEE_IVA = Decimal("0.19")
ROUND_STEP = Decimal("100")


def public_total(
    base: Decimal | float | int | str,
    *,
    percent: Decimal | float | str = DEFAULT_FEE_PERCENT,
    fixed: Decimal | float | str = DEFAULT_FEE_FIXED,
    iva: Decimal | float | str = DEFAULT_FEE_IVA,
) -> Decimal:
    """Monto que paga el comprador para que, tras la tarifa de la pasarela, quede el precio base.

    La tarifa se calcula sobre el total cobrado (porcentaje + fijo + IVA sobre esa comisión).
    El resultado se redondea hacia arriba al siguiente múltiplo de 100 (16.235 → 16.300).
    """
    base_amount = Decimal(str(base or 0)).quantize(Decimal("0.01"))
    if base_amount <= 0:
        return Decimal("0.00")

    rate = (Decimal(str(percent)) * (Decimal("1") + Decimal(str(iva)))).quantize(Decimal("0.0000001"))
    fixed_gross = (Decimal(str(fixed)) * (Decimal("1") + Decimal(str(iva)))).quantize(Decimal("0.01"))
    if rate >= 1:
        raw = base_amount + fixed_gross
    else:
        raw = (base_amount + fixed_gross) / (Decimal("1") - rate)
    units = (raw / ROUND_STEP).to_integral_value(rounding=ROUND_CEILING)
    return (units * ROUND_STEP).quantize(Decimal("0.01"))
