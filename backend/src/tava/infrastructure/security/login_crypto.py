"""Cifrado RSA efímero para que la contraseña no viaje en texto plano en el cliente."""
import base64
import logging

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger("tava.login_crypto")

_private_key = None
_public_key_pem: str | None = None


def _ensure_keys() -> None:
    global _private_key, _public_key_pem
    if _private_key is not None:
        return
    _private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _public_key_pem = (
        _private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    logger.info("Par de claves RSA de login generado (sesión del proceso)")


def get_public_key_pem() -> str:
    _ensure_keys()
    return _public_key_pem or ""


def decrypt_password(encrypted_b64: str) -> str:
    _ensure_keys()
    try:
        data = base64.b64decode(encrypted_b64, validate=True)
        plain = _private_key.decrypt(  # type: ignore[union-attr]
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return plain.decode("utf-8")
    except Exception as e:
        raise ValueError("No se pudo descifrar la contraseña") from e
