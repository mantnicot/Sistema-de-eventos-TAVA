import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.auth import AuthUseCase
from tava.config import get_settings
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.services.captcha import verify_captcha
from tava.presentation.api.dependencies import get_current_user
from tava.presentation.api.http_errors import raise_system_error, raise_user_error
from tava.infrastructure.security.login_crypto import decrypt_password, get_public_key_pem
from tava.presentation.api.schemas import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger("tava.auth")

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.get("/public-key")
async def auth_public_key():
    """Clave pública RSA para cifrar la contraseña en el navegador antes del login."""
    return {"public_key_pem": get_public_key_pem()}


def _resolve_password(body: LoginRequest | RegisterRequest) -> str:
    if body.password_encrypted:
        return decrypt_password(body.password_encrypted)
    return body.password or ""


def _user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        phone=user.phone,
        email_verified=getattr(user, "email_verified", True),
    )


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    try:
        uc = AuthUseCase(db)
        await uc.verify_email(token)
        return {"message": "Correo verificado correctamente. Ya puedes iniciar sesión.", "success": True}
    except ValueError as e:
        raise_user_error(400, "VERIFY_FAILED", str(e))
    except SQLAlchemyError:
        logger.exception("Verificación falló (base de datos)")
        raise_system_error(503, "DATABASE_ERROR", "Error al verificar el correo")
    except Exception:
        logger.exception("Verificación falló (sistema)")
        raise_system_error(500, "VERIFY_ERROR", "Error interno al verificar el correo")


@router.post("/resend-verification")
async def resend_verification(email: str = Query(...), db: AsyncSession = Depends(get_db)):
    try:
        uc = AuthUseCase(db)
        verify_url, email_sent = await uc.resend_verification(email)
        if email_sent:
            msg = "Te enviamos un nuevo enlace de verificación a tu correo."
            link = None
        else:
            msg = (
                "No se pudo enviar el correo (revisa SMTP en Render). "
                "Usa el enlace de verificación mostrado abajo."
            )
            link = verify_url
        return {
            "message": msg,
            "success": True,
            "email_sent": email_sent,
            "verification_url": link,
        }
    except ValueError as e:
        raise_user_error(400, "RESEND_FAILED", str(e))
    except SQLAlchemyError:
        logger.exception("Reenvío de verificación falló (base de datos)")
        raise_system_error(503, "DATABASE_ERROR", "Error de base de datos")
    except Exception:
        logger.exception("Reenvío de verificación falló (sistema)")
        raise_system_error(500, "RESEND_ERROR", "Error interno al reenviar")


@router.post("/register", response_model=RegisterResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(body.captcha_token):
        raise_user_error(400, "CAPTCHA_INVALID", "Verificación captcha inválida")
    try:
        plain_password = _resolve_password(body)
    except ValueError as e:
        raise_user_error(400, "PASSWORD_DECRYPT_FAILED", str(e))
    try:
        uc = AuthUseCase(db)
        user, verify_url, email_sent = await uc.register(
            email=body.email,
            password=plain_password,
            full_name=body.full_name,
            phone=body.phone,
            document_id=body.document_id,
        )
        logger.info("Registro pendiente de verificación: %s (email_sent=%s)", user.email, email_sent)
        if email_sent:
            msg = "Revisa tu correo y haz clic en el enlace para activar tu cuenta."
        else:
            msg = (
                "Cuenta creada. El servidor aún no envía correos: usa el enlace de verificación "
                "que aparece abajo para activar tu cuenta."
            )
        return RegisterResponse(
            message=msg,
            user=_user_response(user),
            email_sent=email_sent,
            verification_url=verify_url if not email_sent else None,
        )
    except ValueError as e:
        logger.info("Registro rechazado (usuario): %s", e)
        raise_user_error(400, "REGISTER_FAILED", str(e))
    except SQLAlchemyError as e:
        logger.exception("Registro falló (base de datos)")
        raise_system_error(503, "DATABASE_ERROR", "No se pudo conectar con la base de datos")
    except Exception:
        logger.exception("Registro falló (sistema)")
        raise_system_error(500, "REGISTER_ERROR", "Error interno al registrar la cuenta")


@router.post("/login", response_model=dict)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(body.captcha_token):
        raise_user_error(400, "CAPTCHA_INVALID", "Verificación captcha inválida")
    try:
        plain_password = _resolve_password(body)
    except ValueError as e:
        raise_user_error(400, "PASSWORD_DECRYPT_FAILED", str(e))
    try:
        uc = AuthUseCase(db)
        user, tokens = await uc.login(body.email, plain_password)
        logger.info("Login exitoso: %s", user.email)
        return {"user": _user_response(user), "tokens": TokenResponse(**tokens)}
    except ValueError as e:
        logger.info("Login rechazado (usuario) %s: %s", body.email, e)
        msg = str(e).lower()
        if "verificar" in msg:
            raise_user_error(403, "EMAIL_NOT_VERIFIED", str(e))
        code = "AUTH_INACTIVE" if "inactivo" in msg else "AUTH_INVALID"
        raise_user_error(401, code, str(e))
    except SQLAlchemyError:
        logger.exception("Login falló (base de datos) %s", body.email)
        raise_system_error(503, "DATABASE_ERROR", "El servidor no pudo acceder a la base de datos")
    except Exception:
        logger.exception("Login falló (sistema) %s", body.email)
        raise_system_error(500, "LOGIN_ERROR", "Error interno al iniciar sesión")


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    try:
        uc = AuthUseCase(db)
        tokens = await uc.refresh(refresh_token)
        return TokenResponse(**tokens)
    except ValueError as e:
        raise_user_error(401, "TOKEN_INVALID", str(e))
    except SQLAlchemyError:
        logger.exception("Refresh token falló (base de datos)")
        raise_system_error(503, "DATABASE_ERROR", "No se pudo validar la sesión")
    except Exception:
        logger.exception("Refresh token falló (sistema)")
        raise_system_error(500, "TOKEN_ERROR", "Error interno al renovar la sesión")


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return _user_response(user)
