from abc import ABC, abstractmethod
from uuid import UUID

from tava.domain.entities.user import User
from tava.domain.enums import UserRole


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def create(
        self,
        email: str,
        password_hash: str,
        full_name: str,
        role: UserRole,
        phone: str | None = None,
        document_id: str | None = None,
    ) -> User: ...

    @abstractmethod
    async def list_by_role(self, role: UserRole | None = None, limit: int = 200, offset: int = 0) -> list[User]: ...
