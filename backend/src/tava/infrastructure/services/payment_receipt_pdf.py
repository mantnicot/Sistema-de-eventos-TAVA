"""Comprobante de pago adjunto al correo. No es una factura electrónica de la DIAN."""
import io
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

GOLD = colors.HexColor("#C9A227")
INK = colors.HexColor("#3A2F2A")
MUTED = colors.HexColor("#6D6158")
BOGOTA = ZoneInfo("America/Bogota")


def _cop(amount: Decimal | float | int | str) -> str:
    number = int(Decimal(str(amount)).quantize(Decimal("1")))
    return f"${number:,}".replace(",", ".")


def build_payment_receipt_pdf(
    *,
    event_name: str,
    event_date: date,
    event_time: time,
    city: str,
    buyer_name: str,
    buyer_email: str,
    ticket_type_name: str,
    quantity: int,
    base_amount: Decimal,
    total_amount: Decimal,
    payment_reference: str | None,
    wompi_transaction_id: str | None,
) -> bytes:
    fee = (Decimal(str(total_amount)) - Decimal(str(base_amount))).quantize(Decimal("0.01"))
    if fee < 0:
        fee = Decimal("0.00")
    paid_at = datetime.now(BOGOTA).strftime("%d/%m/%Y %H:%M")
    when = f"{event_date.strftime('%d/%m/%Y')} · {event_time.strftime('%H:%M')}"

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 64

    pdf.setFillColor(GOLD)
    pdf.rect(0, height - 18, width, 18, fill=1, stroke=0)
    pdf.setFillColor(INK)
    pdf.setFont("Times-Bold", 22)
    pdf.drawString(48, y, "TAVA Teatro")
    y -= 28
    pdf.setFont("Times-Bold", 16)
    pdf.drawString(48, y, "Comprobante de pago")
    y -= 18
    pdf.setFillColor(MUTED)
    pdf.setFont("Times-Roman", 10)
    pdf.drawString(48, y, "Sirve para revisar el cobro. No reemplaza la boleta ni es una factura electrónica.")
    y -= 28

    rows = [
        ("Función", event_name),
        ("Fecha", when),
        ("Ciudad", city),
        ("Comprador", buyer_name),
        ("Correo", buyer_email),
        ("Boleta", f"{quantity} × {ticket_type_name}"),
        ("Valor de las boletas", _cop(base_amount)),
        ("Costo de la pasarela", _cop(fee)),
        ("Total pagado", _cop(total_amount)),
        ("Estado", "Pagado"),
        ("Referencia", payment_reference or "—"),
        ("Transacción Wompi", wompi_transaction_id or "—"),
        ("Registrado", paid_at),
    ]
    pdf.setStrokeColor(GOLD)
    pdf.line(48, y + 12, width - 48, y + 12)
    for label, value in rows:
        pdf.setFillColor(MUTED)
        pdf.setFont("Times-Roman", 11)
        pdf.drawString(48, y, label)
        pdf.setFillColor(INK)
        pdf.setFont("Times-Bold", 11)
        pdf.drawRightString(width - 48, y, str(value)[:72])
        y -= 22
    pdf.line(48, y + 10, width - 48, y + 10)
    y -= 16
    pdf.setFillColor(MUTED)
    pdf.setFont("Times-Italic", 9)
    pdf.drawString(48, y, "El ingreso al teatro se valida con el código QR de la boleta, no con este comprobante.")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
