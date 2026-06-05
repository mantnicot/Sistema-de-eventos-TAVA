"""Envío de correos: API HTTP (Brevo/Resend) en producción; SMTP solo en desarrollo local."""
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

_last_failure: str = ""


def last_email_failure() -> str:
    return _last_failure


def _set_failure(msg: str) -> None:
    global _last_failure
    _last_failure = msg
    logger.error(msg)


def _clean_secret(value: str) -> str:
    return value.strip().strip('"').strip("'").replace(" ", "")


def _smtp_login_email() -> str:
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


def _sender_parts() -> tuple[str, str]:
    raw = (settings.email_from or "").strip()
    angle = _EMAIL_IN_ANGLE.search(raw)
    if angle:
        email = angle.group(1).strip().lower()
        name = raw[: angle.start()].strip() or "TAVA Teatro"
        return name, email
    login = _smtp_login_email()
    if login:
        return "TAVA Teatro", login
    return "TAVA Teatro", "no-reply@tavateatro.com"


def smtp_configured() -> bool:
    return bool(
        settings.smtp_host.strip()
        and _smtp_login_email()
        and _clean_secret(settings.smtp_password)
    )


def resend_configured() -> bool:
    return bool(settings.resend_api_key.strip())


def brevo_configured() -> bool:
    return bool(settings.brevo_api_key.strip())


def smtp_allowed() -> bool:
    """Render y la mayoría de PaaS bloquean puertos SMTP 25/465/587."""
    if settings.email_enable_smtp:
        return smtp_configured()
    if settings.app_env == "production":
        return False
    return smtp_configured()


def http_email_configured() -> bool:
    return resend_configured() or brevo_configured()


def email_transport_ready() -> bool:
    return http_email_configured() or smtp_allowed()


def email_status_summary() -> dict:
    login = _smtp_login_email()
    name, sender_email = _sender_parts()
    return {
        "smtp_configured": smtp_configured(),
        "smtp_allowed": smtp_allowed(),
        "smtp_blocked_on_render": settings.app_env == "production" and not settings.email_enable_smtp,
        "resend_configured": resend_configured(),
        "brevo_configured": brevo_configured(),
        "http_ready": http_email_configured(),
        "smtp_host": settings.smtp_host.strip() or None,
        "smtp_port": settings.smtp_port,
        "smtp_login_email": login or None,
        "sender_email": sender_email,
        "sender_name": name,
        "email_from": (settings.email_from or "").strip() or None,
        "frontend_url": settings.frontend_url.strip() or None,
        "last_failure": last_email_failure() or None,
    }


def _from_header() -> str:
    name, email = _sender_parts()
    return f"{name} <{email}>"


def _envelope_sender() -> str:
    return _sender_parts()[1]


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


async def _send_brevo(to_email: str, subject: str, html: str, text: str) -> bool:
    api_key = settings.brevo_api_key.strip()
    if not api_key:
        return False
    name, sender_email = _sender_parts()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": api_key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json={
                    "sender": {"name": name, "email": sender_email},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "htmlContent": html,
                    "textContent": text,
                },
            )
        if response.is_success:
            return True
        _set_failure(f"Brevo HTTP {response.status_code}: {response.text[:400]}")
        return False
    except Exception as exc:
        _set_failure(f"Brevo error: {exc}")
        return False


async def _send_resend(to_email: str, subject: str, html: str, text: str) -> bool:
    api_key = settings.resend_api_key.strip()
    if not api_key:
        return False
    from_addr = _from_header()
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
        _set_failure(f"Resend HTTP {response.status_code}: {response.text[:400]}")
        return False
    except Exception as exc:
        _set_failure(f"Resend error: {exc}")
        return False


async def send_verification_email(to_email: str, full_name: str, verify_url: str) -> bool:
    """Devuelve True si el correo se envió."""
    global _last_failure
    _last_failure = ""
    subject, html, text = _verification_content(full_name, verify_url)

    if not email_transport_ready():
        _set_failure(
            "Correo no configurado. En Render define BREVO_API_KEY (recomendado) o RESEND_API_KEY. "
            "SMTP Gmail no funciona en Render (puertos bloqueados)."
        )
        return False

    if brevo_configured():
        if await _send_brevo(to_email, subject, html, text):
            logger.info("Correo enviado vía Brevo a %s", to_email)
            return True
        logger.warning("Brevo falló; probando otros transportes")

    if resend_configured():
        if await _send_resend(to_email, subject, html, text):
            logger.info("Correo enviado vía Resend a %s", to_email)
            return True
        logger.warning("Resend falló; probando SMTP si está permitido")

    if smtp_allowed():
        try:
            await asyncio.to_thread(_send_smtp_sync, to_email, subject, html, text)
            logger.info("Correo enviado vía SMTP a %s", to_email)
            return True
        except smtplib.SMTPAuthenticationError as exc:
            _set_failure(f"SMTP autenticación falló: {exc}")
        except OSError as exc:
            if getattr(exc, "errno", None) == 101:
                _set_failure(
                    "Render bloquea SMTP (Network unreachable). Usa BREVO_API_KEY en variables de entorno."
                )
            else:
                _set_failure(f"SMTP red error: {exc}")
        except smtplib.SMTPException as exc:
            _set_failure(f"SMTP error: {exc}")
        except Exception as exc:
            _set_failure(f"SMTP error inesperado: {exc}")
    elif smtp_configured():
        _set_failure(
            "SMTP configurado pero deshabilitado en producción (Render bloquea puerto 587). "
            "Añade BREVO_API_KEY o RESEND_API_KEY."
        )

    return False
