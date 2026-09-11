"""Liquidación de comisión pre/post evento y bloqueo de ingreso."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.event_timing import BOGOTA_TZ, event_end_datetime, event_start_datetime
from tava.domain.enums import EventStatus, PaymentStatus
from tava.infrastructure.persistence.models import EventModel, OrderModel, UserModel
from tava.infrastructure.services.email import (
    send_commission_adjustment_email,
    send_commission_settlement_email,
)


class SettlementUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def sales_bruto(self, event_id: UUID) -> Decimal:
        result = await self._session.execute(
            select(func.coalesce(func.sum(OrderModel.total_amount), 0)).where(
                OrderModel.event_id == event_id,
                OrderModel.payment_status == PaymentStatus.PAID,
            )
        )
        return Decimal(str(result.scalar_one() or 0)).quantize(Decimal("0.01"))

    def fee_for(self, bruto: Decimal, rate: Decimal | None) -> Decimal:
        if not rate or bruto <= 0:
            return Decimal("0.00")
        return (bruto * Decimal(str(rate))).quantize(Decimal("0.01"))

    async def settlement_snapshot(self, event: EventModel) -> dict:
        bruto = await self.sales_bruto(event.id)
        rate = event.commission_rate
        fee = self.fee_for(bruto, rate)
        pre_fee = event.pre_settlement_fee or Decimal("0")
        adjustment = (fee - Decimal(str(pre_fee))).quantize(Decimal("0.01"))
        return {
            "event_id": str(event.id),
            "event_name": event.name,
            "commission_rate": float(rate) if rate is not None else None,
            "bruto": float(bruto),
            "fee_due": float(fee),
            "pre_settlement_bruto": float(event.pre_settlement_bruto) if event.pre_settlement_bruto is not None else None,
            "pre_settlement_fee": float(event.pre_settlement_fee) if event.pre_settlement_fee is not None else None,
            "pre_settlement_notified_at": event.pre_settlement_notified_at.isoformat()
            if event.pre_settlement_notified_at
            else None,
            "pre_settlement_confirmed_at": event.pre_settlement_confirmed_at.isoformat()
            if event.pre_settlement_confirmed_at
            else None,
            "entry_unlocked": bool(event.entry_unlocked),
            "post_settlement_bruto": float(event.post_settlement_bruto)
            if event.post_settlement_bruto is not None
            else None,
            "post_settlement_fee": float(event.post_settlement_fee) if event.post_settlement_fee is not None else None,
            "post_settlement_notified_at": event.post_settlement_notified_at.isoformat()
            if event.post_settlement_notified_at
            else None,
            "adjustment_after_pre": float(adjustment),
            "requires_commission": rate is not None and Decimal(str(rate)) > 0,
        }

    async def confirm_pre_settlement(self, event_id: UUID, admin_id: UUID) -> dict:
        event = await self._session.get(EventModel, event_id)
        if not event:
            raise ValueError("Evento no encontrado")
        if event.commission_rate is None:
            raise ValueError("Este evento no tiene comisión configurada")
        bruto = await self.sales_bruto(event.id)
        fee = self.fee_for(bruto, event.commission_rate)
        now = datetime.now(BOGOTA_TZ)
        if event.pre_settlement_fee is None:
            event.pre_settlement_bruto = bruto
            event.pre_settlement_fee = fee
        event.pre_settlement_confirmed_at = now
        event.pre_settlement_confirmed_by = admin_id
        event.entry_unlocked = True
        await self._session.flush()
        return await self.settlement_snapshot(event)

    async def process_due_notifications(self) -> dict:
        """T-1h: avisar liquidación y bloquear ingreso. Post-evento: ajuste."""
        now = datetime.now(BOGOTA_TZ)
        result = await self._session.execute(
            select(EventModel).where(
                EventModel.commission_rate.is_not(None),
                EventModel.status.notin_([EventStatus.DRAFT, EventStatus.CANCELLED]),
            )
        )
        events = list(result.scalars().all())
        pre_sent = 0
        post_sent = 0

        for event in events:
            details = event.theatrical_details if isinstance(event.theatrical_details, dict) else None
            start = event_start_datetime(event.event_date, event.event_time)
            end = event_end_datetime(event.event_date, event.event_time, details)
            window_start = start - timedelta(hours=1)

            if (
                event.pre_settlement_notified_at is None
                and now >= window_start
                and now < start
            ):
                await self._notify_pre_settlement(event)
                pre_sent += 1

            if (
                event.post_settlement_notified_at is None
                and now >= end
                and event.pre_settlement_notified_at is not None
            ):
                await self._notify_post_adjustment(event)
                post_sent += 1

        await self._session.flush()
        return {"pre_sent": pre_sent, "post_sent": post_sent}

    async def _organizer_and_admins(self, event: EventModel) -> list[UserModel]:
        recipients: list[UserModel] = []
        org = await self._session.get(UserModel, event.organizer_id)
        if org and org.email:
            recipients.append(org)
        admins = (
            await self._session.execute(
                select(UserModel).where(
                    UserModel.is_platform_admin.is_(True),
                    UserModel.is_active.is_(True),
                )
            )
        ).scalars().all()
        seen = {u.id for u in recipients}
        for admin in admins:
            if admin.id not in seen and admin.email:
                recipients.append(admin)
                seen.add(admin.id)
        return recipients

    async def _notify_pre_settlement(self, event: EventModel) -> None:
        bruto = await self.sales_bruto(event.id)
        fee = self.fee_for(bruto, event.commission_rate)
        event.pre_settlement_bruto = bruto
        event.pre_settlement_fee = fee
        event.pre_settlement_notified_at = datetime.now(BOGOTA_TZ)
        # Bloquear ingreso hasta confirmación del admin general
        if not event.pre_settlement_confirmed_at:
            event.entry_unlocked = False

        rate_pct = float(Decimal(str(event.commission_rate or 0)) * 100)
        recipients = await self._organizer_and_admins(event)
        for user in recipients:
            await send_commission_settlement_email(
                to_email=user.email,
                full_name=user.full_name,
                event_name=event.name,
                event_date=event.event_date.isoformat(),
                event_time=event.event_time.isoformat(timespec="minutes"),
                bruto=float(bruto),
                fee=float(fee),
                rate_percent=rate_pct,
                role_hint="organizador" if user.id == event.organizer_id else "admin",
            )

    async def _notify_post_adjustment(self, event: EventModel) -> None:
        bruto = await self.sales_bruto(event.id)
        fee = self.fee_for(bruto, event.commission_rate)
        pre_fee = Decimal(str(event.pre_settlement_fee or 0))
        adjustment = (fee - pre_fee).quantize(Decimal("0.01"))
        event.post_settlement_bruto = bruto
        event.post_settlement_fee = fee
        event.post_settlement_notified_at = datetime.now(BOGOTA_TZ)

        if adjustment == 0:
            return

        rate_pct = float(Decimal(str(event.commission_rate or 0)) * 100)
        recipients = await self._organizer_and_admins(event)
        for user in recipients:
            await send_commission_adjustment_email(
                to_email=user.email,
                full_name=user.full_name,
                event_name=event.name,
                bruto=float(bruto),
                total_fee=float(fee),
                already_billed=float(pre_fee),
                adjustment=float(adjustment),
                rate_percent=rate_pct,
            )
