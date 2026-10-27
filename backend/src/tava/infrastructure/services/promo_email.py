"""Plantillas HTML de publicidad (revista / un evento)."""
from __future__ import annotations

from html import escape

from tava.config import get_settings


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


def _event_card(ev: dict, frontend: str) -> str:
    name = escape(str(ev.get("name") or "Evento"))
    when = escape(str(ev.get("when") or ""))
    city = escape(str(ev.get("city") or ""))
    blurb = escape(str(ev.get("blurb") or "")[:220])
    img = escape(_abs_media(ev.get("image_url")))
    link = f"{frontend}/eventos/{ev['id']}"
    where = " · ".join(p for p in (when, city) if p)
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;background:#ffffff;border:1px solid rgba(201,162,39,0.35);border-radius:12px;overflow:hidden;">
      <tr><td><img src="{img}" alt="" width="560" style="display:block;width:100%;max-height:180px;object-fit:cover;" /></td></tr>
      <tr><td style="padding:14px 16px 18px;font-family:Georgia,serif;color:#3a2f2a;">
        <h3 style="margin:0 0 6px;font-size:20px;color:#8a6410;">{name}</h3>
        <p style="margin:0 0 10px;font-size:13px;color:#6d6158;font-family:Arial,sans-serif;">{where}</p>
        <p style="margin:0 0 14px;font-size:14px;line-height:1.45;">{blurb}</p>
        <a href="{link}" style="display:inline-block;background:linear-gradient(135deg,#ffd86b,#b8860b);color:#2a1f12;text-decoration:none;font-family:Arial,sans-serif;font-weight:700;font-size:14px;padding:10px 16px;border-radius:999px;">Comprar boletas</a>
      </td></tr>
    </table>
    """


def build_promo_html(
    *,
    format: str,
    subject: str,
    intro: str,
    events: list[dict],
) -> tuple[str, str]:
    settings = get_settings()
    frontend = settings.frontend_url.rstrip("/")
    intro_safe = escape((intro or "").strip()) or "Te compartimos la cartelera de TAVA Teatro."
    unsub = f"{frontend}/perfil"
    header = f"""
    <div style="background:#3a2f2a;color:#e8d49b;text-align:center;padding:18px 16px 14px;font-family:Georgia,serif;">
      <div style="letter-spacing:0.28em;font-size:18px;font-weight:700;">TAVA</div>
      <div style="margin-top:6px;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#c9a0a8;font-family:Arial,sans-serif;">Teatro · Boletería</div>
    </div>
    """
    foot = f"""
    <div style="padding:16px;text-align:center;font-family:Arial,sans-serif;font-size:12px;color:#6d6158;border-top:1px solid rgba(201,162,39,0.25);">
      Recibes este correo porque autorizaste publicidad de TAVA Teatro.<br/>
      <a href="{unsub}" style="color:#9e5a6b;">Gestionar preferencias / dejar de recibir publicidad</a>
      · <a href="{frontend}" style="color:#9e5a6b;">Ir al sitio</a>
    </div>
    """

    if format == "spotlight" and events:
        ev = events[0]
        name = escape(str(ev.get("name") or "Evento"))
        when = escape(str(ev.get("when") or ""))
        city = escape(str(ev.get("city") or ""))
        address = escape(str(ev.get("address") or ""))
        blurb = escape(str(ev.get("blurb") or "")[:320])
        img = escape(_abs_media(ev.get("image_url")))
        link = f"{frontend}/eventos/{ev['id']}"
        place = " · ".join(p for p in (when, address or city) if p)
        body = f"""
        <img src="{img}" alt="" width="560" style="display:block;width:100%;max-height:260px;object-fit:cover;" />
        <div style="padding:20px 18px 24px;text-align:center;font-family:Georgia,serif;color:#3a2f2a;">
          <h2 style="margin:0 0 8px;font-size:26px;color:#8a6410;">{name}</h2>
          <p style="margin:0 0 12px;font-size:14px;color:#9e5a6b;font-family:Arial,sans-serif;">{place}</p>
          <p style="margin:0 auto 18px;max-width:28rem;font-size:15px;line-height:1.5;color:#6d6158;">{blurb or intro_safe}</p>
          <a href="{link}" style="display:inline-block;background:linear-gradient(135deg,#ffd86b,#b8860b);color:#2a1f12;text-decoration:none;font-family:Arial,sans-serif;font-weight:700;font-size:15px;padding:12px 20px;border-radius:999px;">Comprar boletas</a>
        </div>
        """
    else:
        cards = "".join(_event_card(ev, frontend) for ev in events)
        body = f"""
        <p style="padding:18px 18px 6px;font-family:Georgia,serif;font-size:15px;line-height:1.5;color:#6d6158;font-style:italic;">{intro_safe}</p>
        <div style="padding:0 12px 8px;">{cards}</div>
        """

    html = f"""<!DOCTYPE html><html><body style="margin:0;background:#ece7df;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:16px 8px;">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="margin:0 auto;background:#faf8f4;border-radius:12px;overflow:hidden;">
      <tr><td>{header}</td></tr>
      <tr><td>{body}</td></tr>
      <tr><td>{foot}</td></tr>
    </table>
    </td></tr></table>
    </body></html>"""

    names = ", ".join(str(e.get("name") or "") for e in events[:4])
    text = f"{subject}\n\n{intro_safe}\n\nEventos: {names}\n\n{frontend}/eventos\n"
    return html, text


async def send_promo_email(to_email: str, subject: str, html: str, text: str) -> bool:
    from tava.infrastructure.services.email import _deliver_email

    return await _deliver_email(to_email, subject, html, text)
