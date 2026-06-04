import secrets

from tava.infrastructure.security.password import hash_password, verify_password


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_verification_token(token: str) -> str:
    return hash_password(token)


def verify_verification_token(plain: str, token_hash: str) -> bool:
    return verify_password(plain, token_hash)
