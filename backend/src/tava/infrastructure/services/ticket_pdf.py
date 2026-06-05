"""Generación de boletas PDF con QR — estilo teatral TAVA."""
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
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.utils import ImageReader

from tava.config import get_settings

settings = get_settings()

PAGE_W, PAGE_H = A4
MARGIN = 1.2 * cm
GOLD = colors.HexColor("#C9A227")
GOLD_DARK = colors.HexColor("#8B6914")
INK = colors.HexColor("#1A1410")
WHITE = colors.white


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
        img = img.filter(ImageFilter.GaussianBlur(radius=16))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception:
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
    pad = 14

    card_bottom = inner_y + pad
    card_top = inner_y + inner_h - pad
    card_h = card_top - card_bottom

    # Marco y fondo blanco
    c.setFillColor(WHITE)
    c.roundRect(inner_x, inner_y, inner_w, inner_h, 14, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(inner_x + 3, inner_y + 3, inner_w - 6, inner_h - 6, 12, fill=0, stroke=1)

    content_x = inner_x + pad + 6
    content_w = inner_w - 2 * (pad + 6)

    # Mitad superior: imagen difuminada de fondo
    hero_h = card_h * 0.48
    hero_bottom = card_top - hero_h

    blurred = _blurred_image_reader(main_image_url, int(content_w * 3), int(hero_h * 3))
    if blurred:
        try:
            c.drawImage(
                blurred,
                content_x,
                hero_bottom,
                width=content_w,
                height=hero_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        except Exception:
            pass

    # Velo blanco sobre la imagen para que el texto se lea bien
    c.setFillColor(Color(1, 1, 1, alpha=0.78))
    c.rect(content_x, hero_bottom, content_w, hero_h, fill=1, stroke=0)

    c.setFillColor(GOLD_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(w / 2, card_top - 0.55 * cm, "TAVA TEATRO · BOLETA OFICIAL")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 20)
    title_y = hero_bottom + hero_h * 0.42
    words = event_name.split()
    line = ""
    title_lines: list[str] = []
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, "Helvetica-Bold", 20) < content_w - 20:
            line = test
        else:
            if line:
                title_lines.append(line)
            line = word
    if line:
        title_lines.append(line)
    for tl in title_lines[:2]:
        c.drawCentredString(w / 2, title_y, tl)
        title_y += 0.8 * cm

    # Zona inferior blanca: detalles + QR + términos (sin solapamientos)
    terms_reserved = 5.2 * cm
    qr_size = 5.6 * cm
    qr_label_h = 0.55 * cm
    qr_padding = 0.45 * cm
    qr_zone_h = qr_size + qr_padding * 2 + qr_label_h
    details_h = 2.4 * cm

    terms_top = card_bottom + terms_reserved
    qr_zone_bottom = terms_top + 0.35 * cm
    qr_zone_top = qr_zone_bottom + qr_zone_h
    details_bottom = qr_zone_top + 0.25 * cm
    details_top = details_bottom + details_h

    # Fondo blanco sólido en zona de contenido inferior
    c.setFillColor(WHITE)
    c.rect(content_x, card_bottom, content_w, details_top - card_bottom, fill=1, stroke=0)

    y = details_top - 0.35 * cm
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, y, f"Asistente: {holder_name}")
    y -= 0.58 * cm
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(GOLD_DARK)
    c.drawCentredString(w / 2, y, f"{ticket_type_name}  ·  ${price:,.0f} COP")
    y -= 0.52 * cm
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#444444"))
    when = f"{event_date.isoformat()} · {event_time.strftime('%H:%M')}"
    c.drawCentredString(w / 2, y, when)
    y -= 0.42 * cm
    c.drawCentredString(w / 2, y, f"{city} — {address}")

    # Zona QR exclusiva — nada puede invadirla
    c.setFillColor(WHITE)
    c.rect(content_x, qr_zone_bottom, content_w, qr_zone_h, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    c.roundRect(content_x + 4, qr_zone_bottom + 2, content_w - 8, qr_zone_h - 4, 6, fill=0, stroke=1)

    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_token)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1A1410", back_color="#FFFFFF")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    qr_x = (w - qr_size) / 2
    qr_y = qr_zone_bottom + qr_padding + qr_label_h * 0.2
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    c.setFillColor(GOLD_DARK)
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(w / 2, qr_zone_bottom + qr_padding * 0.35, "Presenta este QR en la entrada")

    # Términos solo debajo del bloque QR
    c.setStrokeColor(colors.HexColor("#E8E8E8"))
    c.setLineWidth(0.5)
    c.line(content_x + 8, terms_top + 0.15 * cm, content_x + content_w - 8, terms_top + 0.15 * cm)

    terms_style = ParagraphStyle(
        "Terms",
        fontName="Helvetica",
        fontSize=6,
        leading=7.5,
        textColor=colors.HexColor("#666666"),
        alignment=TA_JUSTIFY,
    )
    terms = Paragraph(_terms_text(event_name, event_date, event_time, age_rating or ""), terms_style)
    terms.wrap(content_w - 16, terms_reserved - 0.3 * cm)
    terms.drawOn(c, content_x + 8, card_bottom + 0.12 * cm)

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
