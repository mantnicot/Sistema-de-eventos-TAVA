import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.tickets import TicketUseCase
from tava.config import get_settings
from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.services.wompi import fetch_transaction, verify_event_checksum, wompi_configured
from tava.presentation.api.dependencies import get_current_user, require_roles

logger = logging.getLogger("tava.payments")
router = APIRouter(prefix="/payments", tags=["Pagos Wompi"])
settings = get_settings()


@router.get("/wompi/status")
async def wompi_status():
    return {
        "configured": wompi_configured(),
        "public_key_prefix": (settings.wompi_public_key[:12] + "...") if settings.wompi_public_key else None,
        "checkout_url": settings.wompi_checkout_url,
    }


@router.get("/orders/{order_id}/status")
async def order_payment_status(
    order_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = TicketUseCase(db)
    try:
        is_admin = user.role == UserRole.ADMIN
        return await uc.get_order_status(order_id, user.id, is_admin)
    except ValueError as e:
        raise HTTPException(status_code=404 if "encontrada" in str(e).lower() else 403, detail=str(e))


@router.post("/wompi/webhook")
async def wompi_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    if not verify_event_checksum(payload):
        logger.warning("Wompi webhook checksum inválido")
        raise HTTPException(status_code=401, detail="Firma de evento inválida")

    event_type = payload.get("event")
    if event_type != "transaction.updated":
        return {"ok": True, "ignored": event_type}

    tx = (payload.get("data") or {}).get("transaction") or {}
    reference = tx.get("reference")
    status = tx.get("status")
    transaction_id = tx.get("id")
    if not reference or not status:
        return {"ok": True, "ignored": "missing_fields"}

    uc = TicketUseCase(db)
    try:
        result = await uc.handle_wompi_transaction_update(reference, status, transaction_id)
        await db.commit()
        logger.info("Wompi webhook %s → %s", reference, result)
        return {"ok": True, **result}
    except Exception:
        await db.rollback()
        logger.exception("Wompi webhook falló para %s", reference)
        raise HTTPException(status_code=500, detail="Error procesando pago")


@router.post("/wompi/confirm/{order_id}")
async def wompi_confirm_from_redirect(
    order_id: UUID,
    transaction_id: str | None = Query(None),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirma pago consultando Wompi (útil en local si el webhook no llega)."""
    if not wompi_configured():
        raise HTTPException(status_code=503, detail="Wompi no configurado")
    uc = TicketUseCase(db)
    try:
        status_data = await uc.get_order_status(order_id, user.id, user.role == UserRole.ADMIN)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if status_data.get("tickets_ready"):
        return status_data

    tx_id = transaction_id or status_data.get("wompi_transaction_id")
    if not tx_id:
        raise HTTPException(status_code=400, detail="Falta id de transacción Wompi")

    tx_data = await fetch_transaction(tx_id)
    if not tx_data:
        raise HTTPException(status_code=502, detail="No se pudo consultar la transacción en Wompi")

    reference = tx_data.get("reference") or status_data.get("payment_reference")
    status = tx_data.get("status") or "PENDING"
    if not reference:
        raise HTTPException(status_code=400, detail="Referencia de pago no encontrada")

    try:
        result = await uc.handle_wompi_transaction_update(reference, status, tx_id)
        await db.commit()
        final = await uc.get_order_status(order_id, user.id, user.role == UserRole.ADMIN)
        return {**final, "wompi_sync": result}
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Confirm Wompi falló order=%s", order_id)
        raise HTTPException(status_code=500, detail="Error confirmando pago")


@router.post("/wompi/simulate/{payment_reference}")
async def wompi_simulate_approved(
    payment_reference: str,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Solo desarrollo: simula pago aprobado sin webhook (admin)."""
    if settings.app_env == "production":
        raise HTTPException(status_code=403, detail="No disponible en producción")
    uc = TicketUseCase(db)
    try:
        result = await uc.handle_wompi_transaction_update(
            payment_reference, "APPROVED", f"sim-{payment_reference}"
        )
        await db.commit()
        return result
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Simulación falló")
