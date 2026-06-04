from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import JWTError, jwt

from tava.config import get_settings
from tava.domain.enums import UserRole

settings = get_settings()


def create_access_token(user_id: UUID, email: str, role: UserRole) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role.value,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token_value() -> str:
    return str(uuid4())


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
