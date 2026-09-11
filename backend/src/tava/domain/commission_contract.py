"""Contrato de comisión TAVA y reglas de tarifa."""
from __future__ import annotations

from decimal import Decimal

CONTRACT_VERSION = "v1.0-2026-comision"
MIN_PAID_TICKET_COP = Decimal("15000")
MIN_COMMISSION_RATE = Decimal("0.08")
MAX_COMMISSION_RATE = Decimal("0.15")

COMMISSION_CONTRACT_TEXT = """
CONTRATO DE USO DE PLATAFORMA Y COMISIÓN POR CANALIZACIÓN DE VENTAS — TAVA TEATRO

Al crear, publicar o gestionar un evento de pago en la plataforma TAVA Teatro (“la Plataforma”),
el Usuario Organizador (“el Organizador”) declara haber leído, entendido y aceptado de forma libre,
expresa e inequívoca las siguientes condiciones:

1. OBJETO. La Plataforma permite difundir el evento, canalizar solicitudes de boletería, registrar
ventas y confirmaciones de pago, emitir comprobantes digitales (correo, código, PDF/QR) y facilitar
el control de acceso. El cobro al público puede realizarse fuera de la pasarela de la Plataforma
(por ejemplo, WhatsApp u otros medios acordados).

2. COMISIÓN. El Organizador se obliga a pagar a TAVA Teatro una comisión igual al porcentaje que
seleccione al crear o actualizar el evento, entre el ocho por ciento (8%) y el quince por ciento (15%),
calculada sobre el valor bruto total de la boletería vendida y/o confirmada a través de la Plataforma
(pedidos registrados, pagos validados en el sistema y/o boletas emitidas por ese canal), sin deducir
costos de publicidad, producción, pasarela u otros.

3. MOMENTO DE PAGO. El Organizador deberá pagar la comisión correspondiente a las ventas acumuladas
antes del inicio del evento, conforme al aviso y liquidación que genere la Plataforma (en particular,
el requerimiento enviado aproximadamente una (1) hora antes de la hora programada). Las ventas
adicionales registradas entre ese momento y el cierre del evento serán ajustadas y cobradas con
posterioridad, mediante notificación o correo electrónico.

4. CONDICIÓN PARA HABILITAR INGRESO. El Organizador reconoce que la habilitación del módulo de
validación e ingreso de asistentes queda condicionada a que el Administrador General de TAVA
confirme en la Plataforma la recepción del pago de la comisión adeudada hasta ese momento. Mientras
no exista dicha confirmación, el acceso por validador podrá permanecer bloqueado.

5. VERACIDAD Y VALIDACIÓN DE PAGOS. El Organizador es responsable de validar en la Plataforma
únicamente pagos efectivamente recibidos. La emisión de boletas (correo, código o envío) tras esa
validación genera obligaciones frente al comprador y cuenta para el cálculo de la comisión.

6. MORA E INCUMPLIMIENTO. Si el Organizador no paga la comisión en los plazos indicados, TAVA podrá,
sin perjuicio de otras acciones: (a) mantener o reactivar el bloqueo del validador; (b) suspender o
retirar el evento de cartelera; (c) retener funcionalidades de emisión o gestión; (d) exigir el capital
adeudado, intereses de mora a la tasa máxima legal permitida y costos de cobro; (e) iniciar cobro
persuasivo, prejurídico o judicial.

7. TOLERANCIA. La tolerancia, demora o acuerdos parciales de TAVA no implican renuncia a derechos ni
novación de la obligación.

8. ACEPTACIÓN ELECTRÓNICA. La casilla de aceptación, el registro del usuario, la fecha y hora, y la
versión del texto constituyen prueba del consentimiento del Organizador, con valor de documento
electrónico.

Versión: {version}.
""".strip()


def contract_text(version: str = CONTRACT_VERSION) -> str:
    return COMMISSION_CONTRACT_TEXT.format(version=version)


def normalize_commission_rate(raw: Decimal | float | str | None) -> Decimal:
    if raw is None:
        raise ValueError("Debes indicar la comisión del sistema (entre 8% y 15%).")
    rate = Decimal(str(raw))
    if rate > 1:
        rate = (rate / Decimal("100")).quantize(Decimal("0.0001"))
    if rate < MIN_COMMISSION_RATE or rate > MAX_COMMISSION_RATE:
        raise ValueError("La comisión debe estar entre 8% y 15%.")
    return rate.quantize(Decimal("0.0001"))


def is_paid_ticket_price(price: Decimal | float | int | None) -> bool:
    return Decimal(str(price or 0)) > 0
