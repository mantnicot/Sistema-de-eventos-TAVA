from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.entities.user import User
from tava.domain.enums import UserRole
from tava.domain.repositories.user_repository import UserRepository
from tava.infrastructure.persistence.models import UserModel


def _to_entity(m: UserModel) -> User:
    return User(
        id=m.id,
        email=m.email,
        full_name=m.full_name,
        role=m.role,
        email_verified=m.email_verified,
        is_active=m.is_active,
        created_at=m.created_at,
        is_platform_admin=bool(getattr(m, "is_platform_admin", False)),
        phone=m.phone,
        document_id=m.document_id,
    )


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email.lower()))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_model_by_email(self, email: str) -> UserModel | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email.lower()))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password_hash: str,
        full_name: str,
        role: UserRole,
        phone: str | None = None,
        document_id: str | None = None,
        email_verified: bool = False,
        *,
        privacy_accepted_at=None,
        privacy_policy_version: str | None = None,
        marketing_opt_in: bool = False,
        marketing_opt_in_at=None,
    ) -> User:
        model = UserModel(
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            phone=phone,
            document_id=document_id,
            email_verified=email_verified,
            privacy_accepted_at=privacy_accepted_at,
            privacy_policy_version=privacy_policy_version,
            marketing_opt_in=marketing_opt_in,
            marketing_opt_in_at=marketing_opt_in_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def update_password(self, user_id: UUID, password_hash: str) -> bool:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.password_hash = password_hash
        await self._session.flush()
        return True

    async def list_by_role(self, role: UserRole | None = None, limit: int = 200, offset: int = 0) -> list[User]:
        q = select(UserModel).order_by(UserModel.created_at.desc()).limit(limit).offset(offset)
        if role:
            q = q.where(UserModel.role == role)
        result = await self._session.execute(q)
        return [_to_entity(m) for m in result.scalars().all()]

    async def update_user(
        self,
        user_id: UUID,
        *,
        role: UserRole | None = None,
        is_active: bool | None = None,
        email_verified: bool | None = None,
    ) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        if not model:
            return None
        if role is not None:
            model.role = role
        if is_active is not None:
            model.is_active = is_active
        if email_verified is not None:
            model.email_verified = email_verified
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)
