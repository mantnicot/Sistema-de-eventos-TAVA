"""Contrato de comisión TAVA y reglas de tarifa."""
from __future__ import annotations

from decimal import Decimal

CONTRACT_VERSION = "v2.0-2026-pago-posterior"
MIN_PAID_TICKET_COP = Decimal("15000")
MIN_COMMISSION_RATE = Decimal("0.08")
MAX_COMMISSION_RATE = Decimal("0.15")

COMMISSION_CONTRACT_TEXT = """
CONTRATO DE USO DE PLATAFORMA, COBRO EN LÍNEA Y PAGO POSTERIOR — TAVA TEATRO

Al crear, publicar o gestionar un evento de pago en la plataforma TAVA Teatro (“la Plataforma”),
el Usuario Organizador (“el Organizador”) declara haber leído, entendido y aceptado de forma libre,
expresa e inequívoca las siguientes condiciones:

1. OBJETO. La Plataforma difunde el evento, vende boletería, cobra al público, emite comprobantes
digitales (correo, código, PDF/QR) y permite el control de acceso. El cobro principal es en línea
(Wompi: PSE, Nequi, tarjeta u otros medios que ofrezca la pasarela). Si ese cobro no puede abrirse,
la compra puede continuar por el WhatsApp de contacto que el Organizador registró en el evento.

2. PRECIO. El Organizador registra el valor que quiere recibir por cada boleta. El precio que ve
el público es mayor: incluye el costo de la pasarela y se redondea hacia arriba a la centena
siguiente. Ese recargo no forma parte de la comisión de TAVA.

3. COMISIÓN. TAVA Teatro retiene el porcentaje que el Organizador elija al crear o actualizar el
evento, entre el ocho por ciento (8%) y el quince por ciento (15%), calculado solo sobre el precio
registrado de las boletas efectivamente pagadas, no sobre el recargo de la pasarela.

4. EL DINERO LO RECIBE TAVA. Los pagos en línea entran a la cuenta de la Plataforma. El Organizador
no cobra directo al público por ese canal y no valida esos pagos uno a uno. La boleta se emite
cuando la pasarela confirma el pago.

5. PAGO AL ORGANIZADOR DESPUÉS DE LA FUNCIÓN. TAVA girará al Organizador, con posterioridad a la
presentación del evento, el valor de las boletas pagadas (precio registrado) menos la comisión
pactada. El Organizador puede consultar en su panel únicamente sus eventos y el estado de esas
ventas. El giro se hace por transferencia; los tiempos bancarios pueden sumar días hábiles después
de la función.

6. RESPALDO POR WHATSAPP. Si el pago en línea falla, el pedido puede enviarse al teléfono del
evento. En ese caso el Organizador solo emite boleta cuando el dinero sí llegó. Esas boletas
también cuentan para la comisión y para el giro posterior.

7. INGRESO. Una boleta pagada y emitida puede validarse en puerta. El ingreso no queda bloqueado
a la espera de que el Organizador le pague la comisión a TAVA, porque el dinero ya está en la
Plataforma.

8. MORA E INCUMPLIMIENTO. Si hay pedidos de respaldo cobrados por fuera y no reportados, o datos
falsos de venta, TAVA podrá suspender el evento, retirar la cartelera y exigir lo adeudado.

9. TOLERANCIA. La tolerancia o demora de TAVA no implica renuncia a estos derechos.

10. ACEPTACIÓN ELECTRÓNICA. La casilla de aceptación, el usuario, la fecha y esta versión del texto
son prueba del consentimiento del Organizador.

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
