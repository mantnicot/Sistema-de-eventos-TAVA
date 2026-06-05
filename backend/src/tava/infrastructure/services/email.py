"""Envío de correos transaccionales (SMTP y/o Resend HTTP)."""
import asyncio
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from tava.config import get_settings

logger = logging.getLogger("tava.email")
settings = get_settings()

_EMAIL_IN_ANGLE = re.compile(r"<([^>]+@[^>]+)>")
_EMAIL_PLAIN = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


def _clean_secret(value: str) -> str:
    """Quita espacios y comillas que a veces se pegan al copiar en Render."""
    return value.strip().strip('"').strip("'").replace(" ", "")


def _smtp_login_email() -> str:
    """
    Gmail exige solo el correo en login/sendmail.
    Acepta: tavateatro@gmail.com o TAVA Teatro <tavateatro@gmail.com>
    """
    raw = settings.smtp_user.strip()
    if not raw:
        return ""
    angle = _EMAIL_IN_ANGLE.search(raw)
    if angle:
        return angle.group(1).strip().lower()
    if "@" in raw and "<" not in raw and ">" not in raw:
        return raw.lower()
    plain = _EMAIL_PLAIN.search(raw)
    if plain:
        return plain.group(0).lower()
    return raw


def smtp_configured() -> bool:
    return bool(
        settings.smtp_host.strip()
        and _smtp_login_email()
        and _clean_secret(settings.smtp_password)
    )


def resend_configured() -> bool:
    return bool(settings.resend_api_key.strip())


def email_transport_ready() -> bool:
    return smtp_configured() or resend_configured()


def email_status_summary() -> dict:
    login = _smtp_login_email()
    return {
        "smtp_configured": smtp_configured(),
        "resend_configured": resend_configured(),
        "smtp_host": settings.smtp_host.strip() or None,
        "smtp_port": settings.smtp_port,
        "smtp_user_raw": settings.smtp_user.strip() or None,
        "smtp_login_email": login or None,
        "smtp_user_format_ok": login == settings.smtp_user.strip().lower()
        if settings.smtp_user.strip()
        else None,
        "email_from": (settings.email_from or "").strip() or None,
        "frontend_url": settings.frontend_url.strip() or None,
    }


def _from_header() -> str:
    login = _smtp_login_email()
    raw = (settings.email_from or "").strip()
    if login and login in raw:
        return raw
    if raw:
        return raw
    if login:
        return f"TAVA Teatro <{login}>"
    return "TAVA Teatro <no-reply@tavateatro.com>"


def _envelope_sender() -> str:
    login = _smtp_login_email()
    if login:
        return login
    match = _EMAIL_IN_ANGLE.search(settings.email_from or "")
    if match:
        return match.group(1).strip()
    return (settings.email_from or "").strip()


def _verification_content(full_name: str, verify_url: str) -> tuple[str, str, str]:
    subject = "Confirma tu correo — TAVA Teatro"
    html = f"""
    <div style="font-family: Georgia, serif; max-width: 520px; margin: 0 auto; color: #3d2a14;">
      <h1 style="color: #b8860b;">TAVA Teatro</h1>
      <p>Hola <strong>{full_name}</strong>,</p>
      <p>Gracias por registrarte. Para activar tu cuenta, confirma tu correo con este enlace único:</p>
      <p><a href="{verify_url}" style="background:#c9a227;color:#3d2a14;padding:12px 24px;border-radius:999px;text-decoration:none;display:inline-block;">Verificar mi correo</a></p>
      <p style="font-size:12px;color:#666;">El enlace expira en {settings.email_verification_expire_hours} horas. Si no creaste esta cuenta, ignora este mensaje.</p>
    </div>
    """
    text = f"Hola {full_name},\n\nVerifica tu cuenta TAVA:\n{verify_url}\n"
    return subject, html, text


def _send_smtp_sync(to_email: str, subject: str, html: str, text: str) -> None:
    password = _clean_secret(settings.smtp_password)
    login = _smtp_login_email()
    if not login:
        raise ValueError("SMTP_USER vacío o sin correo válido")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _from_header()
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    sender = _envelope_sender()
    host = settings.smtp_host.strip()
    port = settings.smtp_port
    timeout = 30

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as server:
            server.login(login, password)
            server.sendmail(sender, [to_email], msg.as_string())
        return

    with smtplib.SMTP(host, port, timeout=timeout) as server:
        server.ehlo()
        if server.has_extn("starttls"):
            server.starttls()
            server.ehlo()
        server.login(login, password)
        server.sendmail(sender, [to_email], msg.as_string())


async def _send_resend(to_email: str, subject: str, html: str, text: str) -> bool:
    api_key = settings.resend_api_key.strip()
    if not api_key:
        return False
    from_addr = settings.email_from.strip() or "TAVA Teatro <onboarding@resend.dev>"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": from_addr,
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
            )
        if response.is_success:
            return True
        logger.error("Resend HTTP %s: %s", response.status_code, response.text[:500])
        return False
    except Exception as exc:
        logger.exception("Resend falló para %s: %s", to_email, exc)
        return False


async def send_verification_email(to_email: str, full_name: str, verify_url: str) -> bool:
    """Devuelve True si el correo se envió. Si falla, devuelve False (no lanza excepción)."""
    subject, html, text = _verification_content(full_name, verify_url)

    if not email_transport_ready():
        logger.warning(
            "Correo NO configurado (SMTP/Resend) — no se envió a %s. Revisa variables en Render.",
            to_email,
        )
        return False

    if resend_configured():
        if await _send_resend(to_email, subject, html, text):
            logger.info("Correo de verificación enviado vía Resend a %s", to_email)
            return True
        logger.warning("Resend falló; intentando SMTP si está disponible")

    if smtp_configured():
        try:
            await asyncio.to_thread(_send_smtp_sync, to_email, subject, html, text)
            logger.info(
                "Correo de verificación enviado vía SMTP a %s (login=%s)",
                to_email,
                _smtp_login_email(),
            )
            return True
        except smtplib.SMTPAuthenticationError as exc:
            logger.error(
                "SMTP autenticación falló (login=%s): %s. Usa SMTP_USER=solo@correo.com y contraseña de aplicación Google.",
                _smtp_login_email(),
                exc,
            )
        except smtplib.SMTPException as exc:
            logger.error("SMTP error para %s: %s", to_email, exc)
        except Exception as exc:
            logger.exception("SMTP falló para %s: %s", to_email, exc)

    return False
