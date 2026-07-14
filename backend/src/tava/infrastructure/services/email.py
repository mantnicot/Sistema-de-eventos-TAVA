"""Envío de correos: API HTTP (Brevo/Resend) en producción; SMTP solo en desarrollo local."""
import asyncio
import base64
import logging
import re
import smtplib
from email.mime.application import MIMEApplication
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
    if settings.brevo_sender_email.strip():
        return (
            settings.brevo_sender_name.strip() or "TAVA Teatro",
            settings.brevo_sender_email.strip().lower(),
        )
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


def _reply_to_email() -> str | None:
    raw = (settings.email_from or "").strip()
    angle = _EMAIL_IN_ANGLE.search(raw)
    if angle:
        return angle.group(1).strip().lower()
    login = _smtp_login_email()
    return login or None


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


def sender_ready() -> bool:
    """Remitente explícito requerido para APIs HTTP (Brevo/Resend)."""
    if not http_email_configured():
        return True
    if settings.brevo_sender_email.strip():
        return True
    if resend_configured() and settings.email_from.strip():
        return True
    if brevo_configured() and settings.email_from.strip():
        return True
    return False


def email_config_hint() -> str | None:
    if not http_email_configured():
        return (
            "Define BREVO_API_KEY o RESEND_API_KEY en Render. "
            "SMTP no funciona en Render."
        )
    if not sender_ready():
        return (
            "Define BREVO_SENDER_EMAIL con un correo verificado en Brevo → Senders & IP."
        )
    _, sender = _sender_parts()
    if brevo_configured() and not settings.brevo_sender_email.strip():
        return (
            f"Usando remitente «{sender}» desde EMAIL_FROM. "
            "Recomendado: BREVO_SENDER_EMAIL verificado en Brevo."
        )
    if sender.endswith("@gmail.com") and brevo_configured():
        return (
            f"Remitente Gmail ({sender}): debe estar verificado en Brevo → Senders & IP."
        )
    return None


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
    return (http_email_configured() and sender_ready()) or smtp_allowed()


def email_status_summary() -> dict:
    login = _smtp_login_email()
    name, sender_email = _sender_parts()
    return {
        "smtp_configured": smtp_configured(),
        "smtp_allowed": smtp_allowed(),
        "smtp_blocked_on_render": settings.app_env == "production" and not settings.email_enable_smtp,
        "resend_configured": resend_configured(),
        "brevo_configured": brevo_configured(),
        "brevo_sender_email": settings.brevo_sender_email.strip() or None,
        "http_ready": http_email_configured(),
        "smtp_host": settings.smtp_host.strip() or None,
        "smtp_port": settings.smtp_port,
        "smtp_login_email": login or None,
        "sender_email": sender_email,
        "sender_name": name,
        "email_from": (settings.email_from or "").strip() or None,
        "frontend_url": settings.frontend_url.strip() or None,
        "sender_ready": sender_ready(),
        "email_config_hint": email_config_hint(),
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


async def _send_brevo(
    to_email: str, subject: str, html: str, text: str, attachment: tuple[str, bytes] | None = None
) -> bool:
    api_key = settings.brevo_api_key.strip()
    if not api_key:
        return False
    name, sender_email = _sender_parts()
    payload: dict = {
        "sender": {"name": name, "email": sender_email},
        "to": [{"email": to_email.lower().strip()}],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
        "tags": ["tava-transactional"],
    }
    reply_to = _reply_to_email()
    if reply_to and reply_to != sender_email:
        payload["replyTo"] = {"email": reply_to, "name": name}
    if attachment:
        payload["attachment"] = [
            {"content": base64.b64encode(attachment[1]).decode(), "name": attachment[0]}
        ]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": api_key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json=payload,
            )
        if response.is_success:
            try:
                body = response.json()
                msg_id = body.get("messageId") or body.get("messageIds")
                logger.info("Brevo OK → %s (messageId=%s, from=%s)", to_email, msg_id, sender_email)
            except Exception:
                logger.info("Brevo OK → %s (from=%s)", to_email, sender_email)
            return True
        detail = response.text[:500]
        if response.status_code == 400 and "sender" in detail.lower():
            _set_failure(
                "Brevo rechazó el remitente. En Render define BREVO_SENDER_EMAIL con un correo "
                "verificado en Brevo → Senders & IP."
            )
        else:
            _set_failure(f"Brevo HTTP {response.status_code}: {detail}")
        return False
    except Exception as exc:
        _set_failure(f"Brevo error: {exc}")
        return False


async def _send_resend(
    to_email: str, subject: str, html: str, text: str, attachment: tuple[str, bytes] | None = None
) -> bool:
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
                    **(
                        {
                            "attachments": [
                                {
                                    "filename": attachment[0],
                                    "content": base64.b64encode(attachment[1]).decode(),
                                }
                            ]
                        }
                        if attachment
                        else {}
                    ),
                },
            )
        if response.is_success:
            return True
        _set_failure(f"Resend HTTP {response.status_code}: {response.text[:400]}")
        return False
    except Exception as exc:
        _set_failure(f"Resend error: {exc}")
        return False


def _send_smtp_with_attachment_sync(
    to_email: str, subject: str, html: str, text: str, attachment: tuple[str, bytes] | None
) -> None:
    password = _clean_secret(settings.smtp_password)
    login = _smtp_login_email()
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = _from_header()
    msg["To"] = to_email
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)
    if attachment:
        part = MIMEApplication(attachment[1], _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=attachment[0])
        msg.attach(part)
    host = settings.smtp_host.strip()
    port = settings.smtp_port
    timeout = 30
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as server:
            server.login(login, password)
            server.sendmail(_envelope_sender(), [to_email], msg.as_string())
        return
    with smtplib.SMTP(host, port, timeout=timeout) as server:
        server.ehlo()
        if server.has_extn("starttls"):
            server.starttls()
            server.ehlo()
        server.login(login, password)
        server.sendmail(_envelope_sender(), [to_email], msg.as_string())


async def _deliver_email(
    to_email: str,
    subject: str,
    html: str,
    text: str,
    attachment: tuple[str, bytes] | None = None,
) -> bool:
    global _last_failure
    _last_failure = ""

    if not email_transport_ready():
        hint = email_config_hint() or (
            "Correo no configurado. En Render define BREVO_API_KEY (recomendado) o RESEND_API_KEY. "
            "SMTP Gmail no funciona en Render (puertos bloqueados)."
        )
        _set_failure(hint)
        return False

    if brevo_configured():
        if await _send_brevo(to_email, subject, html, text, attachment):
            logger.info("Correo enviado vía Brevo a %s", to_email)
            return True
        logger.warning("Brevo falló; probando otros transportes")

    if resend_configured():
        if await _send_resend(to_email, subject, html, text, attachment):
            logger.info("Correo enviado vía Resend a %s", to_email)
            return True
        logger.warning("Resend falló; probando SMTP si está permitido")

    if smtp_allowed():
        try:
            if attachment:
                await asyncio.to_thread(
                    _send_smtp_with_attachment_sync, to_email, subject, html, text, attachment
                )
            else:
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


async def send_verification_email(to_email: str, full_name: str, verify_url: str) -> bool:
    subject, html, text = _verification_content(full_name, verify_url)
    return await _deliver_email(to_email, subject, html, text)


def _password_reset_content(full_name: str, reset_url: str) -> tuple[str, str, str]:
    subject = "Restablece tu contraseña — TAVA Teatro"
    html = f"""
    <div style="font-family: Georgia, serif; max-width: 520px; margin: 0 auto; color: #3d2a14;">
      <h1 style="color: #b8860b;">TAVA Teatro</h1>
      <p>Hola <strong>{full_name}</strong>,</p>
      <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta TAVA.</p>
      <p><a href="{reset_url}" style="background:#c9a227;color:#3d2a14;padding:12px 24px;border-radius:999px;text-decoration:none;display:inline-block;">Nueva contraseña</a></p>
      <p style="font-size:12px;color:#666;">El enlace expira en {settings.password_reset_expire_hours} horas. Si no solicitaste este cambio, ignora este mensaje.</p>
    </div>
    """
    text = f"Hola {full_name},\n\nRestablece tu contraseña TAVA:\n{reset_url}\n"
    return subject, html, text


async def send_password_reset_email(to_email: str, full_name: str, reset_url: str) -> bool:
    subject, html, text = _password_reset_content(full_name, reset_url)
    return await _deliver_email(to_email, subject, html, text)


def _tickets_email_html(
    full_name: str,
    event_name: str,
    quantity: int,
    *,
    is_seller_copy: bool = False,
    event_date: str = "",
    event_time: str = "",
    claim_code: str | None = None,
) -> str:
    role = "confirmación de venta" if is_seller_copy else "confirmación de compra"
    when = f"{event_date} · {event_time}" if event_date else "Consulta tu boleta adjunta"
    claim_html = (
        f"""
            <div style="background:#fff8df;border:1px dashed #c9a227;border-radius:10px;padding:14px 18px;margin:0 0 20px;text-align:center;">
              <p style="margin:0 0 6px;font-size:13px;color:#6b5344;">Código para reclamar boletas en tu cuenta</p>
              <p style="margin:0;font-family:monospace;font-size:20px;font-weight:700;color:#6b1a2a;letter-spacing:0.08em;">{claim_code}</p>
              <p style="margin:8px 0 0;font-size:12px;color:#6b5344;">Entra o regístrate en TAVA, abre Mi perfil y pega este código en el recuadro de reclamo.</p>
            </div>
        """
        if claim_code
        else ""
    )
    return f"""
<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:0;background:#1a1410;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:linear-gradient(180deg,#1a1410 0%,#2d2218 50%,#1a1410 100%);padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;background:#fffefb;border-radius:16px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,0.45);">
        <tr>
          <td style="background:linear-gradient(135deg,#6b1a2a,#3d0f18);padding:28px 32px;text-align:center;">
            <p style="margin:0 0 6px;font-family:Georgia,serif;font-size:11px;letter-spacing:0.2em;color:#e8d49b;text-transform:uppercase;">Grupo TAVA</p>
            <h1 style="margin:0;font-family:Georgia,serif;font-size:28px;color:#c9a227;font-weight:700;">🎭 TAVA Teatro</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 36px;font-family:Georgia,serif;color:#3d2a14;line-height:1.65;">
            <p style="margin:0 0 16px;font-size:16px;">Hola <strong style="color:#6b1a2a;">{full_name}</strong>,</p>
            <p style="margin:0 0 20px;font-size:15px;">Adjuntamos tu <strong>{role}</strong> de <strong>{quantity}</strong> boleta(s) para:</p>
            <div style="background:linear-gradient(145deg,#f8f0e4,#fffefb);border:2px solid #c9a227;border-radius:12px;padding:20px 24px;margin:0 0 24px;text-align:center;">
              <p style="margin:0 0 8px;font-size:22px;font-weight:700;color:#8b6914;">{event_name}</p>
              <p style="margin:0;font-size:14px;color:#6b5344;">📅 {when}</p>
            </div>
            {claim_html}
            <p style="margin:0 0 12px;font-size:14px;">El PDF adjunto incluye el <strong>código QR</strong> para validar tu ingreso.</p>
            <p style="margin:0;font-size:13px;color:#6b5344;font-style:italic;">Llega con 30 minutos de anticipación. ¡Nos vemos en el teatro!</p>
          </td>
        </tr>
        <tr>
          <td style="background:#f0e6d4;padding:18px 32px;text-align:center;border-top:1px dashed #c9a227;">
            <p style="margin:0;font-family:Georgia,serif;font-size:12px;color:#6b5344;">
              @tavateatro · Experiencias en vivo
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_tickets_confirmation_email(
    to_email: str,
    full_name: str,
    event_name: str,
    quantity: int,
    pdf_bytes: bytes,
    *,
    is_seller_copy: bool = False,
    event_date: str = "",
    event_time: str = "",
    claim_code: str | None = None,
) -> bool:
    role = "confirmación de venta" if is_seller_copy else "confirmación de compra"
    subject = f"🎭 Boletas {event_name} — TAVA Teatro"
    html = _tickets_email_html(
        full_name,
        event_name,
        quantity,
        is_seller_copy=is_seller_copy,
        event_date=event_date,
        event_time=event_time,
        claim_code=claim_code,
    )
    claim_line = (
        f"\nCódigo para reclamar boletas en tu cuenta: {claim_code}\n"
        "Entra o regístrate en TAVA, abre Mi perfil y pega este código en el recuadro de reclamo.\n"
        if claim_code
        else ""
    )
    text = f"Hola {full_name},\n\nAdjuntamos tu {role} de {quantity} boleta(s) para {event_name}.{claim_line}\n"
    filename = f"boletas-{event_name.replace(' ', '-')[:40]}.pdf"
    return await _deliver_email(to_email, subject, html, text, (filename, pdf_bytes))


def _event_change_email_html(
    full_name: str,
    event_name: str,
    changes: list[str],
    *,
    event_date: str = "",
    event_time: str = "",
    frontend_url: str = "",
) -> str:
    changes_html = "".join(f"<li>{c}</li>" for c in changes)
    when = f"{event_date} · {event_time}" if event_date else "Revisa el PDF adjunto"
    profile_link = f'{frontend_url}/perfil' if frontend_url else "/perfil"
    return f"""
<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:0;background:#1a1410;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#1a1410;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;background:#fffefb;border-radius:16px;overflow:hidden;">
        <tr>
          <td style="background:linear-gradient(135deg,#6b1a2a,#3d0f18);padding:24px;text-align:center;">
            <h1 style="margin:0;font-family:Georgia,serif;font-size:24px;color:#c9a227;">Actualización de evento</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;font-family:Georgia,serif;color:#3d2a14;line-height:1.6;">
            <p>Hola <strong>{full_name}</strong>,</p>
            <p>Hubo cambios en el evento <strong>{event_name}</strong> para el que tienes boleta(s):</p>
            <ul style="padding-left:1.2rem;">{changes_html}</ul>
            <p><strong>Nueva función:</strong> {when}</p>
            <p>Tus boletas fueron <strong>regeneradas</strong> con nuevos códigos QR. Descarga el PDF adjunto o entra a
            <a href="{profile_link}">Mis boletas</a> en TAVA.</p>
            <p style="font-size:13px;color:#6b5344;">Los QR anteriores ya no son válidos para ingresar.</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_event_change_email(
    to_email: str,
    full_name: str,
    event_name: str,
    changes: list[str],
    *,
    pdf_bytes: bytes | None = None,
    event_date: str = "",
    event_time: str = "",
    frontend_url: str = "",
) -> bool:
    subject = f"⚠️ Cambio en «{event_name}» — nuevas boletas TAVA"
    html = _event_change_email_html(
        full_name,
        event_name,
        changes,
        event_date=event_date,
        event_time=event_time,
        frontend_url=frontend_url,
    )
    text = (
        f"Hola {full_name},\n\n"
        f"Hubo cambios en {event_name}:\n"
        + "\n".join(f"- {c}" for c in changes)
        + "\n\nDescarga tus boletas actualizadas en TAVA.\n"
    )
    attachment = None
    if pdf_bytes:
        filename = f"boletas-actualizadas-{event_name.replace(' ', '-')[:30]}.pdf"
        attachment = (filename, pdf_bytes)
    return await _deliver_email(to_email, subject, html, text, attachment)


async def send_ticket_cancelled_email(
    to_email: str,
    full_name: str,
    event_name: str,
    holder_name: str,
    ticket_code: str | None,
) -> bool:
    code_line = f" (código #{ticket_code})" if ticket_code else ""
    subject = f"Boleta cancelada — {event_name}"
    html = f"""
    <div style="font-family:Georgia,serif;max-width:520px;margin:0 auto;color:#3d2a14;">
      <h1 style="color:#b8860b;">TAVA Teatro</h1>
      <p>Hola <strong>{full_name}</strong>,</p>
      <p>Te informamos que la boleta de <strong>{holder_name}</strong>{code_line} para
      <strong>{event_name}</strong> fue <strong>cancelada</strong> por el organizador.</p>
      <p>Si tienes dudas, contáctanos por nuestros canales oficiales.</p>
    </div>
    """
    text = f"Hola {full_name},\n\nTu boleta para {event_name} fue cancelada.\n"
    return await _deliver_email(to_email, subject, html, text)


async def send_event_broadcast_email(
    to_email: str,
    full_name: str,
    event_name: str,
    subject: str,
    message: str,
) -> bool:
    full_subject = subject if subject else f"Mensaje de TAVA — {event_name}"
    html = f"""
    <div style="font-family:Georgia,serif;max-width:520px;margin:0 auto;color:#3d2a14;">
      <h1 style="color:#b8860b;">TAVA Teatro</h1>
      <p>Hola <strong>{full_name}</strong>,</p>
      <p>Mensaje sobre el evento <strong>{event_name}</strong>:</p>
      <div style="background:#f8f0e4;border-left:4px solid #c9a227;padding:16px 20px;margin:16px 0;">
        {message.replace(chr(10), '<br>')}
      </div>
      <p style="font-size:12px;color:#666;">Equipo TAVA Teatro</p>
    </div>
    """
    text = f"Hola {full_name},\n\n{message}\n\n— TAVA Teatro ({event_name})\n"
    return await _deliver_email(to_email, full_subject, html, text)
