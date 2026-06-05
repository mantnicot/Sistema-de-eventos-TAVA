from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.config import get_settings
from tava.domain.enums import UserRole
from tava.infrastructure.persistence.models import EmailVerificationTokenModel, RefreshTokenModel, UserModel
from tava.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from tava.infrastructure.security.jwt import create_access_token, create_refresh_token_value
from tava.infrastructure.security.password import hash_password, verify_password
from tava.infrastructure.security.verification_tokens import (
    generate_verification_token,
    hash_verification_token,
    verify_verification_token,
)
from tava.infrastructure.services.email import send_verification_email

settings = get_settings()


class AuthUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._users = SQLAlchemyUserRepository(session)

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        phone: str | None = None,
        document_id: str | None = None,
        role: UserRole = UserRole.GENERAL,
    ):
        if await self._users.get_by_email(email):
            raise ValueError("El correo ya está registrado")
        user = await self._users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            phone=phone,
            document_id=document_id,
            email_verified=False,
        )
        raw_token = await self._create_verification_token(user.id)
        verify_url = f"{settings.frontend_url.rstrip('/')}/verificar-email?token={raw_token}"
        email_sent = await send_verification_email(user.email, user.full_name, verify_url)
        if not email_sent:
            result = await self._session.execute(select(UserModel).where(UserModel.id == user.id))
            pending = result.scalar_one_or_none()
            if pending:
                await self._session.delete(pending)
                await self._session.flush()
            raise ValueError(
                "Falló el envío del correo. Vamos revisando cómo solucionarlo; inténtalo de nuevo en un rato."
            )
        return user, email_sent

    async def _create_verification_token(self, user_id: UUID) -> str:
        raw = generate_verification_token()
        expires = datetime.now(UTC) + timedelta(hours=settings.email_verification_expire_hours)
        self._session.add(
            EmailVerificationTokenModel(
                user_id=user_id,
                token_hash=hash_verification_token(raw),
                expires_at=expires,
            )
        )
        await self._session.flush()
        return raw

    async def verify_email(self, token: str) -> None:
        if not token or len(token) < 20:
            raise ValueError("Enlace de verificación inválido")
        result = await self._session.execute(
            select(EmailVerificationTokenModel).where(EmailVerificationTokenModel.used_at.is_(None))
        )
        matched = None
        for row in result.scalars().all():
            if verify_verification_token(token, row.token_hash):
                matched = row
                break
        if not matched:
            raise ValueError("Enlace de verificación inválido o ya utilizado")
        if matched.expires_at < datetime.now(UTC):
            raise ValueError("El enlace de verificación ha expirado")
        user_result = await self._session.execute(select(UserModel).where(UserModel.id == matched.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("Usuario no encontrado")
        user.email_verified = True
        matched.used_at = datetime.now(UTC)
        await self._session.flush()

    async def resend_verification(self, email: str) -> bool:
        model = await self._users.get_model_by_email(email)
        if not model:
            raise ValueError("Si el correo existe, recibirás un nuevo enlace")
        if model.email_verified:
            raise ValueError("Este correo ya está verificado")
        raw_token = await self._create_verification_token(model.id)
        verify_url = f"{settings.frontend_url.rstrip('/')}/verificar-email?token={raw_token}"
        email_sent = await send_verification_email(model.email, model.full_name, verify_url)
        if not email_sent:
            raise ValueError(
                "Falló el envío del correo. Vamos revisando cómo solucionarlo; inténtalo de nuevo en un rato."
            )
        return email_sent

    async def login(self, email: str, password: str):
        model = await self._users.get_model_by_email(email)
        if not model or not verify_password(password, model.password_hash):
            raise ValueError("Credenciales inválidas")
        if not model.is_active:
            raise ValueError("Usuario inactivo")
        if not model.email_verified and model.role != UserRole.ADMIN:
            raise ValueError("Debes verificar tu correo antes de ingresar")
        user = await self._users.get_by_id(model.id)
        tokens = await self._issue_tokens(model.id, model.email, model.role)
        return user, tokens

    async def _issue_tokens(self, user_id: UUID, email: str, role: UserRole) -> dict:
        access = create_access_token(user_id, email, role)
        refresh_value = create_refresh_token_value()
        token_hash = hash_password(refresh_value)
        expires = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        self._session.add(
            RefreshTokenModel(user_id=user_id, token_hash=token_hash, expires_at=expires)
        )
        await self._session.flush()
        return {"access_token": access, "refresh_token": refresh_value, "token_type": "bearer"}

    async def refresh(self, refresh_token: str) -> dict:
        result = await self._session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.revoked.is_(False),
                RefreshTokenModel.expires_at > datetime.now(UTC),
            )
        )
        for row in result.scalars().all():
            if verify_password(refresh_token, row.token_hash):
                user_result = await self._session.execute(
                    select(UserModel).where(UserModel.id == row.user_id)
                )
                user = user_result.scalar_one()
                return await self._issue_tokens(user.id, user.email, user.role)
        raise ValueError("Refresh token inválido")
