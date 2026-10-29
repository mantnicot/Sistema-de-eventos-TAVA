"""Plantillas HTML de publicidad: varios eventos o uno solo."""
from __future__ import annotations

from html import escape
from urllib.parse import quote

from tava.config import get_settings

WHATSAPP = "573003268095"
INSTAGRAM = "https://www.instagram.com/tavateatro/"
TIKTOK = "https://www.tiktok.com/@tavateatro"
WINE = "#6d1018"
YELLOW = "#ffe14a"
INK = "#1c2433"
CREAM = "#f4f0ea"
FONT = "'Montserrat','Segoe UI',Helvetica,Arial,sans-serif"


def _abs_media(url: str | None) -> str:
    settings = get_settings()
    raw = (url or "").strip()
    if not raw:
        return f"{settings.frontend_url.rstrip('/')}/logo-tava.png"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    base = (settings.api_public_base_url or "").rstrip("/")
    if not base and settings.app_env == "production":
        base = "https://tava-api-1.onrender.com"
    if raw.startswith("/"):
        return f"{base}{raw}" if base else raw
    return f"{base}/{raw}" if base else raw


def _meta(ev: dict) -> str:
    parts = [str(ev.get("time_label") or "").strip(), str(ev.get("place") or "").strip(), str(ev.get("cost") or "").strip()]
    return "  |  ".join(part for part in parts if part)


def _maps(ev: dict) -> str:
    query = " ".join(
        part for part in (str(ev.get("address") or "").strip(), str(ev.get("city") or "").strip(), "Colombia") if part
    )
    return "https://www.google.com/maps/search/?api=1&query=" + quote(query or "Bogotá")


def _badge(ev: dict) -> str:
    weekday = escape(str(ev.get("weekday") or ""))
    day = escape(str(ev.get("day") or ""))
    month = escape(str(ev.get("month") or ""))
    return f"""
    <div style="display:inline-block;background:{YELLOW};border-radius:9px;padding:6px 8px 7px;text-align:center;font-family:{FONT};color:#1a1208;line-height:1;">
      <div style="font-size:10px;font-weight:700;letter-spacing:0.08em;">{weekday}</div>
      <div style="margin-top:1px;font-size:20px;font-weight:800;letter-spacing:-0.03em;">{day}</div>
      <div style="margin-top:1px;font-size:11px;font-weight:600;letter-spacing:0.02em;">{month}</div>
    </div>
    """


def _photo(ev: dict, height: int) -> str:
    img = escape(_abs_media(ev.get("image_url")))
    badge = _badge(ev)
    return f"""
    <div style="position:relative;height:{height}px;overflow:hidden;background:transparent;border-radius:16px 16px 0 0;line-height:0;">
      <img src="{img}" alt="" width="640" style="display:block;width:100%;height:{height}px;object-fit:cover;border:0;border-radius:16px 16px 0 0;" />
      <div style="position:absolute;top:8px;left:8px;line-height:normal;">{badge}</div>
    </div>
    """


def _grid_card(ev: dict, frontend: str) -> str:
    name = escape(str(ev.get("name") or "Evento").upper())
    meta = escape(_meta(ev))
    link = f"{frontend}/eventos/{ev.get('id')}"
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:transparent;border-collapse:separate;border-spacing:0;">
      <tr><td style="padding:0;background:transparent;border-radius:16px 16px 0 0;overflow:hidden;line-height:0;">
        <a href="{link}" style="text-decoration:none;color:{INK};">{_photo(ev, 128)}</a>
      </td></tr>
      <tr><td style="background:{CREAM};padding:13px 12px 15px;border-radius:0 0 16px 16px;font-family:{FONT};">
        <a href="{link}" style="text-decoration:none;color:{INK};">
          <div style="font-size:13px;font-weight:800;letter-spacing:0.03em;line-height:1.2;">{name}</div>
          <div style="margin-top:5px;font-size:10px;font-weight:600;letter-spacing:0.06em;line-height:1.35;color:#3e4652;text-transform:uppercase;">{meta}</div>
        </a>
      </td></tr>
    </table>
    """


def _rows_of_three(events: list[dict], frontend: str) -> str:
    rows: list[str] = []
    for start in range(0, len(events), 3):
        chunk = events[start : start + 3]
        cells = []
        for ev in chunk:
            cells.append(
                f'<td width="33%" valign="top" style="width:33%;padding:7px;background:transparent;">{_grid_card(ev, frontend)}</td>'
            )
        while len(cells) < 3:
            cells.append('<td width="33%" style="width:33%;padding:7px;background:transparent;"></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:0;background:transparent;">'
        + "".join(rows)
        + "</table>"
    )


def _button(href: str, label: str, *, outline: bool = False) -> str:
    safe = escape(label)
    if outline:
        style = (
            f"display:block;padding:13px 18px;border:1.5px solid #f7efe8;border-radius:16px;"
            f"color:#ffffff;font-family:{FONT};font-size:13px;font-weight:700;"
            "letter-spacing:0.05em;text-align:center;text-decoration:none;text-transform:uppercase;"
        )
    else:
        style = (
            f"display:block;padding:14px 20px;background:{YELLOW};border-radius:999px;"
            f"color:#1a1208;font-family:{FONT};font-size:14px;font-weight:700;"
            "letter-spacing:0.05em;text-align:center;text-decoration:none;text-transform:uppercase;"
        )
    return f'<a href="{href}" style="{style}">{safe}</a>'


def _shell(inner: str, *, recipient_email: str, frontend: str) -> str:
    mail = escape((recipient_email or "correo@gmail.com").upper())
    unsub = f"{frontend}/perfil"
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
</head>
<body style="margin:0;padding:0;background:{WINE};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{WINE};">
  <tr><td align="center" style="padding:32px 18px 40px;">
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:transparent;">
      <tr><td align="center" style="padding:4px 12px 22px;font-family:{FONT};color:#ffffff;">
        <div style="font-size:26px;font-weight:800;letter-spacing:0.24em;">TAVA</div>
        <div style="margin-top:7px;font-size:11px;font-weight:500;letter-spacing:0.32em;">TEATRO · BOLETERÍA</div>
      </td></tr>
      <tr><td style="padding:0 4px 4px;background:transparent;">{inner}</td></tr>
      <tr><td style="padding:28px 28px 0;text-align:center;font-family:{FONT};font-size:12px;font-weight:400;line-height:1.7;color:#f6ecec;">
        Este correo ha sido enviado para {mail}. Si no deseas continuar recibiendo esta información,
        haz clic en el siguiente <a href="{unsub}" style="color:#ffffff;text-decoration:underline;">link</a> para cancelar tu suscripción.
        <br/><br/>
        Por favor, NO respondas a este mensaje, este es un medio informativo automático.
        <br/><br/>
        <a href="{frontend}" style="color:#ffffff;text-decoration:underline;">Ver Políticas de Uso y seguridad</a>
        · <a href="{frontend}" style="color:#ffffff;text-decoration:underline;">Ver Políticas de Privacidad Ley de Datos Personales</a>
        <br/><br/>
        Este email fue enviado por: TAVA TEATRO
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def build_promo_html(
    *,
    format: str,
    subject: str,
    intro: str,
    events: list[dict],
    direct: bool = False,
    recipient_name: str = "",
    recipient_email: str = "",
) -> tuple[str, str]:
    del intro, direct
    settings = get_settings()
    frontend = settings.frontend_url.rstrip("/")
    name = escape((recipient_name or "").strip())
    hello = f"Hola {name}" if name else "Hola"
    whatsapp_publish = (
        f"https://wa.me/{WHATSAPP}?text=" + quote("Hola TAVA Teatro, quiero publicar un evento.")
    )

    if format == "spotlight" and events:
        ev = events[0]
        title = escape(str(ev.get("name") or "Evento").upper())
        meta = escape(_meta(ev))
        blurb = escape(str(ev.get("blurb") or "")[:360])
        link = f"{frontend}/eventos/{ev.get('id')}"
        greeting = f"{hello}, este es el último evento que no te puedes perder"
        body = f"""
        <p style="margin:0 18px 20px;text-align:center;font-family:{FONT};font-size:20px;line-height:1.45;font-weight:600;letter-spacing:-0.01em;color:#ffffff;">{greeting}</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:transparent;border-collapse:separate;border-spacing:0;">
          <tr><td style="padding:0;border-radius:18px 18px 0 0;overflow:hidden;background:transparent;">{_photo(ev, 268)}</td></tr>
          <tr><td style="background:{CREAM};padding:24px 28px 26px;border-radius:0 0 18px 18px;font-family:{FONT};color:{INK};">
            <div style="font-size:26px;font-weight:800;letter-spacing:0.02em;line-height:1.15;">{title}</div>
            <div style="margin-top:8px;font-size:13px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#3e4652;">{meta}</div>
            <p style="margin:16px 0 22px;font-size:15px;font-weight:400;line-height:1.6;color:#3a4250;">{blurb}</p>
            {_button(link, "Compra tu boleta aquí")}
          </td></tr>
        </table>
        <div style="height:18px;line-height:18px;">&nbsp;</div>
        {_button(f"{frontend}/eventos", "Conoce los otros eventos en cartelera", outline=True)}
        <p style="margin:18px 0 0;text-align:center;font-family:{FONT};font-size:14px;font-weight:500;letter-spacing:0.02em;color:#ffffff;">
          <a href="{_maps(ev)}" style="color:#ffffff;text-decoration:none;">Cómo llegar</a>
          <span style="padding:0 6px;opacity:0.7;">·</span>
          <a href="{INSTAGRAM}" style="color:#ffffff;text-decoration:none;">Instagram @tavateatro</a>
          <span style="padding:0 6px;opacity:0.7;">·</span>
          <a href="{TIKTOK}" style="color:#ffffff;text-decoration:none;">TikTok @tavateatro</a>
        </p>
        """
    else:
        greeting = f"{hello}, estos son los eventos que no te puedes perder"
        grid = _rows_of_three(events, frontend)
        body = f"""
        <p style="margin:0 12px 18px;text-align:center;font-family:{FONT};font-size:20px;line-height:1.45;font-weight:600;letter-spacing:-0.01em;color:#ffffff;">{greeting}</p>
        {grid}
        <div style="height:18px;line-height:18px;">&nbsp;</div>
        {_button(f"{frontend}/eventos", "Conoce cada evento y compra tu boleta aquí")}
        <div style="height:12px;line-height:12px;">&nbsp;</div>
        {_button(whatsapp_publish, "¿Tienes un evento que quieres publicar? Contáctanos", outline=True)}
        """

    html = _shell(body, recipient_email=recipient_email, frontend=frontend)
    names = ", ".join(str(event.get("name") or "") for event in events[:6])
    text = (
        f"{subject}\n\n{hello},\n\nEventos: {names}\n\n{frontend}/eventos\n"
    )
    return html, text


async def send_promo_email(to_email: str, subject: str, html: str, text: str) -> bool:
    from tava.infrastructure.services.email import _deliver_email

    return await _deliver_email(to_email, subject, html, text)
