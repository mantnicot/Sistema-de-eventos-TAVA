"""Generación de boletas PDF con QR — estilo teatral TAVA."""
import io
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.utils import ImageReader

from tava.config import get_settings

settings = get_settings()

PAGE_W, PAGE_H = A4
MARGIN = 1.4 * cm
GOLD = colors.HexColor("#C9A227")
GOLD_DARK = colors.HexColor("#8B6914")
VELVET = colors.HexColor("#1A1410")
CREAM = colors.HexColor("#F5E6C8")
BURGUNDY = colors.HexColor("#6B1A2A")


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


def _resolve_image_reader(image_url: str | None) -> ImageReader | None:
    if not image_url:
        return None
    raw = image_url.strip()

    if raw.startswith("http"):
        try:
            import httpx

            response = httpx.get(raw, timeout=15, follow_redirects=True)
            if response.is_success and response.content:
                return ImageReader(io.BytesIO(response.content))
        except Exception:
            pass
        path_part = urlparse(raw).path
        if path_part.startswith("/uploads/"):
            raw = path_part

    if raw.startswith("/uploads/"):
        p = Path(settings.uploads_dir) / raw.removeprefix("/uploads/").lstrip("/")
        if p.is_file():
            return ImageReader(str(p))
    p = Path(raw)
    if p.is_file():
        return ImageReader(str(p))
    return None


def _draw_ticket_page(
    c: canvas.Canvas,
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
    qr_token: str,
    holder_name: str,
) -> None:
    w, h = PAGE_W, PAGE_H
    inner_x = MARGIN
    inner_y = MARGIN
    inner_w = w - 2 * MARGIN
    inner_h = h - 2 * MARGIN

    # Fondo velvet con marco dorado
    c.setFillColor(VELVET)
    c.roundRect(inner_x, inner_y, inner_w, inner_h, 14, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.roundRect(inner_x + 4, inner_y + 4, inner_w - 8, inner_h - 8, 12, fill=0, stroke=1)
    c.setStrokeColor(GOLD_DARK)
    c.setLineWidth(0.8)
    c.roundRect(inner_x + 10, inner_y + 10, inner_w - 20, inner_h - 20, 10, fill=0, stroke=1)

    # Banda superior decorativa
    band_h = 1.1 * cm
    c.setFillColor(BURGUNDY)
    c.roundRect(inner_x + 14, inner_y + inner_h - band_h - 18, inner_w - 28, band_h, 6, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(w / 2, inner_y + inner_h - band_h - 10, "TAVA TEATRO · BOLETA OFICIAL")

    y = inner_y + inner_h - 2.2 * cm

    # Imagen del evento
    img_reader = _resolve_image_reader(main_image_url)
    img_h = 4.2 * cm
    if img_reader:
        try:
            c.drawImage(
                img_reader,
                inner_x + 22,
                y - img_h,
                width=inner_w - 44,
                height=img_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            y -= img_h + 0.35 * cm
        except Exception:
            y -= 0.2 * cm
    else:
        y -= 0.2 * cm

    # Nombre del evento — grande y teatral
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 26)
    title_lines = []
    words = event_name.split()
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, "Helvetica-Bold", 26) < inner_w - 50:
            line = test
        else:
            if line:
                title_lines.append(line)
            line = word
    if line:
        title_lines.append(line)
    for tl in title_lines[:2]:
        c.drawCentredString(w / 2, y, tl)
        y -= 0.95 * cm

    y -= 0.15 * cm
    c.setFillColor(CREAM)
    c.setFont("Helvetica", 11)
    c.drawCentredString(w / 2, y, f"Asistente: {holder_name}")
    y -= 0.65 * cm

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(GOLD)
    c.drawCentredString(w / 2, y, f"{ticket_type_name}  ·  ${price:,.0f} COP")
    y -= 0.7 * cm

    c.setFillColor(CREAM)
    c.setFont("Helvetica", 10)
    when = f"{event_date.isoformat()} · {event_time.strftime('%H:%M')}"
    c.drawCentredString(w / 2, y, when)
    y -= 0.5 * cm
    c.drawCentredString(w / 2, y, f"{city} — {address}")
    y -= 0.9 * cm

    # QR en marco dorado
    qr = qrcode.QRCode(version=1, box_size=8, border=1)
    qr.add_data(qr_token)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#C9A227", back_color="#1A1410")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_size = 3.8 * cm
    qr_x = (w - qr_size) / 2
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(qr_x - 6, y - qr_size - 6, qr_size + 12, qr_size + 12, 8, fill=0, stroke=1)
    c.drawImage(ImageReader(qr_buf), qr_x, y - qr_size, width=qr_size, height=qr_size, mask="auto")
    y -= qr_size + 0.55 * cm

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(w / 2, y, "Presenta este QR en la entrada")
    y -= 1.1 * cm

    # Línea decorativa
    c.setStrokeColor(GOLD_DARK)
    c.setLineWidth(0.5)
    c.line(inner_x + 30, y, w - inner_x - 30, y)
    y -= 0.5 * cm

    # Términos
    terms_style = ParagraphStyle(
        "Terms",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor("#B8A88A"),
        alignment=TA_JUSTIFY,
    )
    terms = Paragraph(_terms_text(event_name, event_date, event_time, age_rating or ""), terms_style)
    tw, th = terms.wrap(inner_w - 50, y - inner_y - 20)
    terms.drawOn(c, inner_x + 25, max(inner_y + 18, y - th))

    c.showPage()


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
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for qr_token, holder_name in tickets:
        _draw_ticket_page(
            c,
            event_name=event_name,
            event_date=event_date,
            event_time=event_time,
            city=city,
            address=address,
            age_rating=age_rating,
            main_image_url=main_image_url,
            ticket_type_name=ticket_type_name,
            price=price,
            qr_token=qr_token,
            holder_name=holder_name,
        )
    c.save()
    return buffer.getvalue()
