"""Generación de boletas PDF con QR (ReportLab + qrcode)."""
import io
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from tava.config import get_settings

settings = get_settings()


def _terms_text(event_name: str, event_date: date, event_time: time, age_rating: str) -> str:
    when = f"{event_date.isoformat()} a las {event_time.strftime('%H:%M')}"
    age = age_rating or "público general"
    return f"""<b>Términos y condiciones</b><br/><br/>
Precios y formas de pago: El precio de los boletos para la obra <b>{event_name}</b> es el establecido por los
medios oficiales y acuerdos de parte del vendedor. El pago puede realizarse en efectivo en el teatro o con
tarjeta de crédito o débito o transferencias bien sea vía NEQUI (300-326-8095) o como se haya acordado con el comprador o en la página oficial de compra.<br/><br/>
Cambios y devoluciones: No se aceptan cambios ni devoluciones de boletos una vez realizada la compra a menos que se cancele o
aplace la obra por situaciones de fuerza mayor.<br/><br/>
Ingreso: La compra de esta boleta no garantiza su ingreso a la función en caso de incumplir los tiempos establecidos por el grupo TAVA o el teatro y las políticas de los mismos.<br/><br/>
Horarios y fechas: La <b>{event_name}</b> se presenta el <b>{when}</b>. Los asistentes deben llegar con 30 minutos de anticipación para asegurar su ingreso.<br/><br/>
Asientos asignados: Los asientos son asignados directamente en el teatro por orden de llegada o como corresponda dependiendo del evento.<br/><br/>
Restricciones de edad y contenido: La <b>{event_name}</b> está destinada a mayores de <b>{age}</b>. Se recomienda solo
asistir bajo este rango superior y bajo la responsabilidad del consumidor no permitir ver el espectáculo a menores.<br/><br/>
Política de cancelación de la obra: En caso de que el evento sea cancelado por alguna razón, se
realizará el reembolso total del precio de los boletos y se hará una explicación y disculpa pública de parte del elenco.<br/><br/>
Política de uso de Imagen: Al adquirir esta boleta usted accede a ser fotografiado o grabado en
audio y/o video para contenido de uso exclusivo por la agrupación TAVA en sus redes sociales, portafolio y
material visual o audiovisual que requiera.<br/><br/>
Responsabilidad del Grupo TAVA: El Grupo NO se hace responsable por daños o lesiones sufridos por los asistentes antes, durante o después de la función.<br/><br/>
Prohibiciones: Se prohíbe fumar, consumir alimentos y bebidas dentro del teatro, así como tomar
fotografías o grabar la obra sin autorización previa; en caso de autorización se prohíbe el uso de flash y/o
otros medios que puedan incomodar o afectar el espectáculo.<br/><br/>
Derechos de autor: La <b>{event_name}</b> está protegida por derechos de autor. Queda prohibida su reproducción total o parcial sin
autorización previa del Grupo TAVA y director TOÑO.<br/><br/>
Al comprar el boleto para <b>{event_name}</b> el cliente acepta y se compromete a
cumplir con los términos y condiciones establecidos; en caso de no estar de acuerdo posee 2 días hábiles después de la compra de la boleta."""


def _resolve_image_path(image_url: str | None) -> Path | None:
    if not image_url:
        return None
    raw = image_url.strip()
    if raw.startswith("http"):
        path_part = urlparse(raw).path
        if path_part.startswith("/uploads/"):
            raw = path_part
    if raw.startswith("/uploads/"):
        p = Path(settings.uploads_dir) / raw.removeprefix("/uploads/").lstrip("/")
        return p if p.is_file() else None
    p = Path(raw)
    return p if p.is_file() else None


def _qr_image(qr_token: str, accent_hex: str) -> Image:
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(qr_token)
    qr.make(fit=True)
    img = qr.make_image(fill_color=accent_hex, back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=4.2 * cm, height=4.2 * cm)


def _accent_from_event(main_image_url: str | None) -> str:
    """Color de acento; futuro: extraer de imagen. Por ahora dorado TAVA."""
    return "#B8860B"


def build_tickets_pdf(
    *,
    event_name: str,
    event_date: date,
    event_time: time,
    city: str,
    address: str,
    age_rating: str | None,
    main_image_url: str | None,
    ticket_type_name: str,
    price: Decimal,
    tickets: list[tuple[str, str]],
) -> bytes:
    """
    tickets: lista de (ticket_id, qr_token, holder_name) — holder en tickets[2] via tuple
    Actually tickets: list of dict or tuple (qr_token, holder_name)
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    styles = getSampleStyleSheet()
    accent = _accent_from_event(main_image_url)
    title_style = ParagraphStyle(
        "EventTitle",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor(accent),
        spaceAfter=8,
        alignment=1,
    )
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12)
    terms_style = ParagraphStyle("Terms", parent=styles["Normal"], fontSize=7, leading=9, textColor=colors.grey)

    img_path = _resolve_image_path(main_image_url)
    story: list = []

    for qr_token, holder_name in tickets:
        if img_path:
            try:
                story.append(Image(str(img_path), width=16 * cm, height=5 * cm))
                story.append(Spacer(1, 0.3 * cm))
            except Exception:
                pass
        story.append(Paragraph(event_name, title_style))
        story.append(Paragraph(f"<b>Asistente:</b> {holder_name}", body))
        story.append(Paragraph(f"<b>Tipo:</b> {ticket_type_name} · <b>Valor:</b> ${price:,.0f} COP", body))
        story.append(
            Paragraph(
                f"<b>Fecha y hora:</b> {event_date.isoformat()} · {event_time.strftime('%H:%M')}<br/>"
                f"<b>Lugar:</b> {city} — {address}",
                body,
            )
        )
        story.append(Spacer(1, 0.4 * cm))
        story.append(_qr_image(qr_token, accent))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("<i>Presenta este QR en la entrada · TAVA Teatro</i>", body))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(_terms_text(event_name, event_date, event_time, age_rating or ""), terms_style))
        story.append(Spacer(1, 1 * cm))

    doc.build(story)
    return buffer.getvalue()
