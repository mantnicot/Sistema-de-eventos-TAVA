"""Cifrado RSA para que la contraseña no viaje en texto plano.

La clave privada se comparte entre workers (site_settings / env). Si cada
proceso genera la suya, el login falla con «No se pudo descifrar la contraseña».
"""
from __future__ import annotations

import base64
import logging
import threading

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger("tava.login_crypto")

LOGIN_KEY_SETTING = "login_rsa_private_pem"

_lock = threading.Lock()
_private_key = None
_public_key_pem: str | None = None


def _public_pem_from_private(private_key) -> str:
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


def _load_private_from_pem(pem: str):
    return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)


def _generate_private():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _private_to_pem(private_key) -> str:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def configure_from_pem(private_pem: str) -> None:
    """Fija la clave privada compartida (arranque / settings)."""
    global _private_key, _public_key_pem
    key = _load_private_from_pem(private_pem.strip())
    with _lock:
        _private_key = key
        _public_key_pem = _public_pem_from_private(key)
    logger.info("Clave RSA de login cargada (compartida)")


def _ensure_keys() -> None:
    global _private_key, _public_key_pem
    if _private_key is not None:
        return
    with _lock:
        if _private_key is not None:
            return
        from tava.config import get_settings

        settings = get_settings()
        env_pem = (getattr(settings, "login_rsa_private_key_pem", None) or "").strip()
        if env_pem:
            _private_key = _load_private_from_pem(env_pem)
            _public_key_pem = _public_pem_from_private(_private_key)
            logger.info("Clave RSA de login desde LOGIN_RSA_PRIVATE_KEY_PEM")
            return
        _private_key = _generate_private()
        _public_key_pem = _public_pem_from_private(_private_key)
        logger.warning(
            "Par RSA de login generado en memoria. "
            "En multi-worker conviene persistirlo (site_settings o LOGIN_RSA_PRIVATE_KEY_PEM)."
        )


def export_private_pem() -> str:
    _ensure_keys()
    return _private_to_pem(_private_key)


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


async def ensure_persisted_login_key(session) -> None:
    """Carga o guarda la clave RSA en site_settings para todos los workers."""
    from sqlalchemy import select

    from tava.config import get_settings
    from tava.infrastructure.persistence.models import SiteSettingModel

    settings = get_settings()
    env_pem = (getattr(settings, "login_rsa_private_key_pem", None) or "").strip()
    if env_pem:
        configure_from_pem(env_pem)
        return

    result = await session.execute(
        select(SiteSettingModel).where(SiteSettingModel.key == LOGIN_KEY_SETTING)
    )
    row = result.scalar_one_or_none()
    if row and (row.value or "").strip():
        configure_from_pem(row.value)
        return

    # Generar una y guardar; si otro worker ganó la carrera, releer la de la base.
    fresh = _generate_private()
    pem = _private_to_pem(fresh)
    try:
        if row:
            row.value = pem
        else:
            session.add(SiteSettingModel(key=LOGIN_KEY_SETTING, value=pem))
        await session.flush()
        configure_from_pem(pem)
        logger.info("Clave RSA de login persistida en site_settings")
    except Exception:
        await session.rollback()
        again = await session.execute(
            select(SiteSettingModel).where(SiteSettingModel.key == LOGIN_KEY_SETTING)
        )
        existing = again.scalar_one_or_none()
        if existing and (existing.value or "").strip():
            configure_from_pem(existing.value)
            logger.info("Clave RSA de login tomada de otro worker")
            return
        configure_from_pem(pem)
        logger.warning("Usando clave RSA local; no se pudo persistir en site_settings")
