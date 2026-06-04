from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from tava.infrastructure.security.jwt import decode_access_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    repo = SQLAlchemyUserRepository(db)
    user = await repo.get_by_id(UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


def require_roles(*roles: UserRole):
    async def checker(user=Depends(get_current_user)):
        if user.role == UserRole.ADMIN:
            return user
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permisos")
        return user

    return checker
