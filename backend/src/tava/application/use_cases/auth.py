from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.config import get_settings
from tava.domain.enums import UserRole
from tava.infrastructure.persistence.models import RefreshTokenModel, UserModel
from tava.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from tava.infrastructure.security.jwt import create_access_token, create_refresh_token_value
from tava.infrastructure.security.password import hash_password, verify_password

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
        )
        tokens = await self._issue_tokens(user.id, user.email, user.role)
        return user, tokens

    async def login(self, email: str, password: str):
        model = await self._users.get_model_by_email(email)
        if not model or not verify_password(password, model.password_hash):
            raise ValueError("Credenciales inválidas")
        if not model.is_active:
            raise ValueError("Usuario inactivo")
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
