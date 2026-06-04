import hashlib
import secrets
from uuid import UUID


def generate_qr_token() -> str:
    return secrets.token_urlsafe(48)


def generate_security_hash(ticket_id: UUID, event_id: UUID, qr_token: str, secret: str) -> str:
    raw = f"{ticket_id}:{event_id}:{qr_token}:{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()


def verify_security_hash(
    ticket_id: UUID, event_id: UUID, qr_token: str, stored_hash: str, secret: str
) -> bool:
    expected = generate_security_hash(ticket_id, event_id, qr_token, secret)
    return secrets.compare_digest(expected, stored_hash)
