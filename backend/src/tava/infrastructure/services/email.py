"""Envío de correos transaccionales (SMTP opcional)."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from tava.config import get_settings

logger = logging.getLogger("tava.email")
settings = get_settings()


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


async def send_verification_email(to_email: str, full_name: str, verify_url: str) -> bool:
    """Devuelve True si el correo se envió por SMTP."""
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

    if not smtp_configured():
        logger.warning(
            "SMTP no configurado — correo NO enviado a %s. Enlace: %s",
            to_email,
            verify_url,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_from, [to_email], msg.as_string())
        logger.info("Correo de verificación enviado a %s", to_email)
        return True
    except Exception:
        logger.exception("No se pudo enviar correo a %s", to_email)
        raise
