"""Integración Wompi — checkout web y validación de webhooks."""
from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from tava.config import get_settings

logger = logging.getLogger("tava.wompi")
settings = get_settings()


def wompi_configured() -> bool:
    return bool(
        settings.wompi_public_key.strip()
        and settings.wompi_integrity_secret.strip()
        and settings.wompi_events_secret.strip()
    )


def amount_in_cents(total_cop: Decimal) -> int:
    return int(total_cop * 100)


def integrity_signature(reference: str, amount_cents: int, currency: str = "COP") -> str:
    chain = f"{reference}{amount_cents}{currency}{settings.wompi_integrity_secret.strip()}"
    return hashlib.sha256(chain.encode("utf-8")).hexdigest()


def build_checkout_url(
    *,
    reference: str,
    amount_cents: int,
    redirect_url: str,
    customer_email: str,
    customer_name: str,
) -> str:
    params = {
        "public-key": settings.wompi_public_key.strip(),
        "currency": "COP",
        "amount-in-cents": str(amount_cents),
        "reference": reference,
        "signature:integrity": integrity_signature(reference, amount_cents),
        "redirect-url": redirect_url,
        "customer-data:email": customer_email,
        "customer-data:full-name": customer_name[:120],
    }
    return f"{settings.wompi_checkout_url.rstrip('/')}/?{urlencode(params)}"


def verify_event_checksum(payload: dict) -> bool:
    signature = payload.get("signature") or {}
    properties: list[str] = signature.get("properties") or []
    expected = (signature.get("checksum") or "").upper()
    if not properties or not expected:
        return False

    data = payload.get("data") or {}
    parts: list[str] = []
    for prop in properties:
        node: object = data
        for key in prop.split("."):
            if not isinstance(node, dict):
                return False
            node = node.get(key)
        parts.append("" if node is None else str(node))

    timestamp = payload.get("timestamp")
    chain = "".join(parts) + str(timestamp) + settings.wompi_events_secret.strip()
    calculated = hashlib.sha256(chain.encode("utf-8")).hexdigest().upper()
    return calculated == expected


async def fetch_transaction(transaction_id: str) -> dict | None:
    if not settings.wompi_public_key.strip():
        return None
    url = f"{settings.wompi_api_base_url.rstrip('/')}/transactions/{transaction_id}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params={"public_key": settings.wompi_public_key.strip()})
        if response.is_success:
            body = response.json()
            return body.get("data") if isinstance(body, dict) else None
    except Exception as exc:
        logger.warning("Wompi fetch transaction failed: %s", exc)
    return None
