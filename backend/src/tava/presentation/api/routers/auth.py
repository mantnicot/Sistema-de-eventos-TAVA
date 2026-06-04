import logging

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.auth import AuthUseCase
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.services.captcha import verify_captcha
from tava.presentation.api.dependencies import get_current_user
from tava.presentation.api.http_errors import raise_system_error, raise_user_error
from tava.presentation.api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse

logger = logging.getLogger("tava.auth")

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        phone=user.phone,
    )


@router.post("/register", response_model=dict)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(body.captcha_token):
        raise_user_error(400, "CAPTCHA_INVALID", "Verificación captcha inválida")
    try:
        uc = AuthUseCase(db)
        user, tokens = await uc.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            phone=body.phone,
            document_id=body.document_id,
        )
        logger.info("Registro exitoso: %s", user.email)
        return {"user": _user_response(user), "tokens": TokenResponse(**tokens)}
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
        uc = AuthUseCase(db)
        user, tokens = await uc.login(body.email, body.password)
        logger.info("Login exitoso: %s", user.email)
        return {"user": _user_response(user), "tokens": TokenResponse(**tokens)}
    except ValueError as e:
        logger.info("Login rechazado (usuario) %s: %s", body.email, e)
        code = "AUTH_INACTIVE" if "inactivo" in str(e).lower() else "AUTH_INVALID"
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
