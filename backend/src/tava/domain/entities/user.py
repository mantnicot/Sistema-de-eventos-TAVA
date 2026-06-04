from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tava.domain.enums import UserRole


@dataclass
class User:
    id: UUID
    email: str
    full_name: str
    role: UserRole
    email_verified: bool
    is_active: bool
    created_at: datetime
    phone: str | None = None
    document_id: str | None = None
