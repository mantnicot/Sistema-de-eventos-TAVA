"""Generación de boletas PDF con QR — layout vertical, una boleta por página A4."""
import io
from datetime import date, time
from decimal import Decimal
from functools import lru_cache
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
MARGIN = 0.55 * cm
GOLD = colors.HexColor("#C9A227")
GOLD_DARK = colors.HexColor("#8B6914")
INK = colors.HexColor("#1A1410")
WHITE = colors.white
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "logo-tava.png"


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


@lru_cache(maxsize=32)
def _load_image_bytes(image_url: str | None) -> bytes | None:
    if not image_url:
        return None
    raw = image_url.strip()

    if raw.startswith("http"):
        try:
            import httpx

            response = httpx.get(raw, timeout=5, follow_redirects=True)
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


def _logo_reader() -> ImageReader | None:
    if not LOGO_PATH.is_file():
        return None
    try:
        return ImageReader(str(LOGO_PATH))
    except Exception:
        return None


def _blurred_image_reader(image_url: str | None, width_px: int, height_px: int) -> ImageReader | None:
    data = _load_image_bytes(image_url)
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img = img.resize((width_px, height_px), Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(radius=14))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception:
        return None


def _draw_dashed_line_horizontal(c: canvas.Canvas, x0: float, x1: float, y: float) -> None:
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.8)
    c.setDash(4, 4)
    c.line(x0, y, x1, y)
    c.setDash()


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


def _draw_terms_paragraph(
    c: canvas.Canvas,
    *,
    event_name: str,
    event_date: date,
    event_time: time,
    age_rating: str | None,
    x: float,
    y: float,
    width: float,
    max_height: float,
) -> None:
    html = _terms_text(event_name, event_date, event_time, age_rating or "")
    font_size = 5.6
    leading = 6.8
    paragraph: Paragraph | None = None

    while font_size >= 4.2:
        style = ParagraphStyle(
            "Terms",
            fontName="Helvetica",
            fontSize=font_size,
            leading=leading,
            textColor=colors.HexColor("#555555"),
            alignment=TA_JUSTIFY,
        )
        paragraph = Paragraph(html, style)
        _, used_h = paragraph.wrap(width, max_height)
        if used_h <= max_height:
            break
        font_size -= 0.2
        leading = font_size + 1.1

    if paragraph is not None:
        paragraph.drawOn(c, x, y)


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
    ticket_code: str,
) -> None:
    w, h = PAGE_W, PAGE_H
    tx, ty = MARGIN, MARGIN
    tw, th = w - 2 * MARGIN, h - 2 * MARGIN
    pad = 0.3 * cm
    inner_x = tx + pad
    inner_w = tw - 2 * pad

    c.setFillColor(WHITE)
    c.roundRect(tx, ty, tw, th, 10, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(tx + 2, ty + 2, tw - 4, th - 4, 8, fill=0, stroke=1)

    logo_h = 1.35 * cm
    terms_h = 8.0 * cm
    qr_h = 8.2 * cm
    info_h = 3.2 * cm
    header_h = th - terms_h - qr_h - info_h - logo_h - pad * 2 - 0.5 * cm

    top_y = ty + th - pad
    header_bottom = top_y - header_h
    info_bottom = header_bottom - info_h
    qr_bottom = info_bottom - qr_h
    terms_bottom = ty + pad + logo_h + 0.25 * cm

    # --- Cabecera con imagen ---
    c.saveState()
    path = c.beginPath()
    path.roundRect(inner_x, header_bottom, inner_w, header_h, 6)
    c.clipPath(path, stroke=0, fill=0)

    blurred = _blurred_image_reader(main_image_url, int(inner_w * 2.5), int(header_h * 2.5))
    if blurred:
        try:
            c.drawImage(
                blurred,
                inner_x,
                header_bottom,
                width=inner_w,
                height=header_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        except Exception:
            c.setFillColor(colors.HexColor("#2A1520"))
            c.rect(inner_x, header_bottom, inner_w, header_h, fill=1, stroke=0)
    else:
        c.setFillColor(colors.HexColor("#2A1520"))
        c.rect(inner_x, header_bottom, inner_w, header_h, fill=1, stroke=0)

    c.setFillColor(Color(0.1, 0.06, 0.08, alpha=0.5))
    c.rect(inner_x, header_bottom, inner_w, header_h, fill=1, stroke=0)
    c.restoreState()

    cx = inner_x + inner_w / 2
    hy = header_bottom + header_h - 0.8 * cm
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(cx, hy, "TAVA TEATRO · BOLETA OFICIAL")
    hy -= 1.0 * cm
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    for line in _wrap_text(c, event_name, "Helvetica-Bold", 18, inner_w - 1.0 * cm)[:3]:
        c.drawCentredString(cx, hy, line)
        hy -= 0.72 * cm

    _draw_dashed_line_horizontal(c, inner_x, inner_x + inner_w, header_bottom)

    # --- Datos del asistente ---
    iy = info_bottom + info_h - 0.7 * cm
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    c.drawCentredString(cx, iy, f"Asistente: {holder_name}")
    iy -= 0.58 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(cx, iy, f"{ticket_type_name} · ${price:,.0f} COP")
    iy -= 0.52 * cm
    c.setFont("Helvetica", 9.5)
    c.drawCentredString(cx, iy, f"{event_date.isoformat()} · {event_time.strftime('%H:%M')}")
    iy -= 0.48 * cm
    venue = f"{city} — {address}" if address else city
    for line in _wrap_text(c, venue, "Helvetica", 9.5, inner_w - 0.8 * cm)[:2]:
        c.drawCentredString(cx, iy, line)
        iy -= 0.42 * cm

    _draw_dashed_line_horizontal(c, inner_x, inner_x + inner_w, info_bottom)

    # --- QR grande + código numérico ---
    c.setFillColor(GOLD_DARK)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(cx, qr_bottom + qr_h - 0.6 * cm, "ESCANEA EL CÓDIGO EN LA ENTRADA")

    qr_size = min(inner_w - 1.6 * cm, qr_h - 3.4 * cm, 6.6 * cm)
    qr = qrcode.QRCode(version=1, box_size=12, border=2)
    qr.add_data(qr_token)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1A1410", back_color="#FFFFFF")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    qr_x = cx - qr_size / 2
    qr_y = qr_bottom + (qr_h - qr_size) / 2 - 0.15 * cm
    c.setFillColor(WHITE)
    c.roundRect(qr_x - 8, qr_y - 8, qr_size + 16, qr_size + 16, 4, fill=1, stroke=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.roundRect(qr_x - 8, qr_y - 8, qr_size + 16, qr_size + 16, 4, fill=0, stroke=1)
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    if ticket_code:
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(cx, qr_bottom + 1.15 * cm, f"Código: {ticket_code}")
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(cx, qr_bottom + 0.55 * cm, "Si el QR falla, dicta este código al validador")

    _draw_dashed_line_horizontal(c, inner_x, inner_x + inner_w, qr_bottom)

    # --- Términos ---
    c.setFillColor(GOLD_DARK)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(cx, terms_bottom + terms_h - 0.35 * cm, "Términos y condiciones — TAVA Teatro")

    terms_x = inner_x + 0.12 * cm
    terms_w = inner_w - 0.24 * cm
    terms_avail_h = terms_h - 0.8 * cm
    _draw_terms_paragraph(
        c,
        event_name=event_name,
        event_date=event_date,
        event_time=event_time,
        age_rating=age_rating,
        x=terms_x,
        y=terms_bottom + 0.12 * cm,
        width=terms_w,
        max_height=terms_avail_h,
    )

    # --- Logo TAVA al pie ---
    logo = _logo_reader()
    logo_size = 1.05 * cm
    logo_x = cx - logo_size / 2
    logo_y = ty + pad + 0.12 * cm
    if logo:
        try:
            c.drawImage(logo, logo_x, logo_y, width=logo_size, height=logo_size, mask="auto")
        except Exception:
            pass
    c.setFillColor(GOLD_DARK)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(cx, logo_y - 0.22 * cm, "Grupo TAVA Teatro")

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
    tickets: list[tuple[str, str, str]],
) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for qr_token, holder_name, ticket_code in tickets:
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
            ticket_code=ticket_code,
        )
    c.save()
    return buffer.getvalue()
