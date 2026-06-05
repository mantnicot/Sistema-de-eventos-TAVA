"""Generación de boletas PDF con QR — layout horizontal tipo entrada."""
import io
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.utils import ImageReader

from tava.config import get_settings

settings = get_settings()

PAGE_W, PAGE_H = A4
MARGIN = 1.0 * cm
GOLD = colors.HexColor("#C9A227")
GOLD_DARK = colors.HexColor("#8B6914")
INK = colors.HexColor("#1A1410")
WHITE = colors.white
PANEL_DARK = colors.HexColor("#2A1520")


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


def _load_image_bytes(image_url: str | None) -> bytes | None:
    if not image_url:
        return None
    raw = image_url.strip()

    if raw.startswith("http"):
        try:
            import httpx

            response = httpx.get(raw, timeout=15, follow_redirects=True)
            if response.is_success and response.content:
                return response.content
        except Exception:
            pass
        path_part = urlparse(raw).path
        if path_part.startswith("/uploads/"):
            raw = path_part

    if raw.startswith("/uploads/"):
        p = Path(settings.uploads_dir) / raw.removeprefix("/uploads/").lstrip("/")
        if p.is_file():
            return p.read_bytes()
    p = Path(raw)
    if p.is_file():
        return p.read_bytes()
    return None


def _blurred_image_reader(image_url: str | None, width_px: int, height_px: int) -> ImageReader | None:
    data = _load_image_bytes(image_url)
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img = img.resize((width_px, height_px), Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(radius=18))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception:
        return None


def _draw_dashed_line_vertical(c: canvas.Canvas, x: float, y0: float, y1: float) -> None:
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.8)
    c.setDash(4, 4)
    c.line(x, y0, x, y1)
    c.setDash()


def _draw_ticket_face(
    c: canvas.Canvas,
    *,
    event_name: str,
    event_date: date,
    event_time: time,
    city: str,
    address: str,
    main_image_url: str | None,
    ticket_type_name: str,
    price: Decimal,
    qr_token: str,
    holder_name: str,
) -> None:
    w, h = PAGE_W, PAGE_H
    ticket_h = 9.2 * cm
    ticket_w = w - 2 * MARGIN
    ticket_x = MARGIN
    ticket_y = h - MARGIN - ticket_h

    left_ratio = 0.62
    left_w = ticket_w * left_ratio
    right_w = ticket_w - left_w
    split_x = ticket_x + left_w

    # Marco exterior
    c.setFillColor(WHITE)
    c.roundRect(ticket_x, ticket_y, ticket_w, ticket_h, 10, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(ticket_x + 2, ticket_y + 2, ticket_w - 4, ticket_h - 4, 8, fill=0, stroke=1)

    # Panel izquierdo: imagen difuminada de fondo (puede quedar bajo el QR stub)
    blurred = _blurred_image_reader(main_image_url, int(left_w * 3), int(ticket_h * 3))
    if blurred:
        try:
            c.drawImage(
                blurred,
                ticket_x + 6,
                ticket_y + 6,
                width=left_w - 12,
                height=ticket_h - 12,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        except Exception:
            pass

    # Oscurecer panel izquierdo para legibilidad del texto
    c.setFillColor(Color(0.12, 0.08, 0.1, alpha=0.55))
    c.roundRect(ticket_x + 6, ticket_y + 6, left_w - 12, ticket_h - 12, 6, fill=1, stroke=0)

    # Panel derecho: blanco sólido (zona QR aislada)
    c.setFillColor(WHITE)
    c.roundRect(split_x, ticket_y + 4, right_w - 4, ticket_h - 8, 6, fill=1, stroke=0)

    _draw_dashed_line_vertical(c, split_x, ticket_y + 8, ticket_y + ticket_h - 8)

    # Texto panel izquierdo
    tx = ticket_x + left_w / 2
    ty = ticket_y + ticket_h - 1.0 * cm
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(tx, ty, "TAVA TEATRO · BOLETA OFICIAL")

    ty -= 0.85 * cm
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 17)
    for line in _wrap_text(c, event_name, "Helvetica-Bold", 17, left_w - 1.2 * cm)[:2]:
        c.drawCentredString(tx, ty, line)
        ty -= 0.72 * cm

    ty -= 0.15 * cm
    c.setFont("Helvetica", 10)
    c.drawCentredString(tx, ty, f"Asistente: {holder_name}")
    ty -= 0.55 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(tx, ty, f"{ticket_type_name} · ${price:,.0f} COP")
    ty -= 0.5 * cm
    c.setFont("Helvetica", 9)
    c.drawCentredString(tx, ty, f"{event_date.isoformat()} · {event_time.strftime('%H:%M')}")
    ty -= 0.42 * cm
    c.drawCentredString(tx, ty, f"{city} — {address}")

    # Panel derecho: QR grande sobre blanco puro
    qr_panel_cx = split_x + right_w / 2
    header_y = ticket_y + ticket_h - 1.15 * cm
    c.setFillColor(GOLD_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(qr_panel_cx, header_y, "ESCANEA EL CÓDIGO")

    qr_size = min(right_w - 1.4 * cm, ticket_h - 2.8 * cm, 6.8 * cm)
    qr = qrcode.QRCode(version=1, box_size=12, border=2)
    qr.add_data(qr_token)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1A1410", back_color="#FFFFFF")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    qr_x = qr_panel_cx - qr_size / 2
    qr_y = ticket_y + (ticket_h - qr_size) / 2 - 0.15 * cm

    # Fondo blanco extra detrás del QR
    c.setFillColor(WHITE)
    c.roundRect(qr_x - 8, qr_y - 8, qr_size + 16, qr_size + 16, 4, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.roundRect(qr_x - 8, qr_y - 8, qr_size + 16, qr_size + 16, 4, fill=0, stroke=1)
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    c.setFillColor(GOLD_DARK)
    c.setFont("Helvetica", 7)
    c.drawCentredString(qr_panel_cx, ticket_y + 0.55 * cm, "Presenta este QR en la entrada")


def _draw_terms_page(
    c: canvas.Canvas,
    *,
    event_name: str,
    event_date: date,
    event_time: time,
    age_rating: str | None,
) -> None:
    inner_x = MARGIN
    inner_w = PAGE_W - 2 * MARGIN
    top_y = PAGE_H - MARGIN - 0.5 * cm
    bottom_y = MARGIN + 0.5 * cm

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(inner_x, top_y, "Términos y condiciones — TAVA Teatro")

    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.line(inner_x, top_y - 0.25 * cm, inner_x + inner_w, top_y - 0.25 * cm)

    terms_style = ParagraphStyle(
        "Terms",
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#444444"),
        alignment=TA_JUSTIFY,
    )
    terms = Paragraph(_terms_text(event_name, event_date, event_time, age_rating or ""), terms_style)
    avail_h = top_y - bottom_y - 1.2 * cm
    terms.wrap(inner_w, avail_h)
    terms.drawOn(c, inner_x, bottom_y)


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: int, max_w: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, font, size) < max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


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
    _draw_ticket_face(
        c,
        event_name=event_name,
        event_date=event_date,
        event_time=event_time,
        city=city,
        address=address,
        main_image_url=main_image_url,
        ticket_type_name=ticket_type_name,
        price=price,
        qr_token=qr_token,
        holder_name=holder_name,
    )
    c.showPage()
    _draw_terms_page(
        c,
        event_name=event_name,
        event_date=event_date,
        event_time=event_time,
        age_rating=age_rating,
    )
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
