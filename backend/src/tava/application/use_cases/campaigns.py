"""Campañas de publicidad por correo — solo administrador de plataforma."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.domain.enums import EventStatus
from tava.infrastructure.persistence.models import (
    EventModel,
    PromoCampaignModel,
    PromoCampaignRecipientModel,
    UserModel,
)
from tava.infrastructure.services.promo_email import build_promo_html, send_promo_email

BATCH_SIZE = 25
VALID_FORMATS = {"magazine", "spotlight"}
VALID_AUDIENCES = {"opt_in", "opt_in_buyers", "opt_in_favorites"}


def _format_when(ev: EventModel) -> str:
    try:
        return f"{ev.event_date.isoformat()} · {ev.event_time.strftime('%H:%M')}"
    except Exception:
        return str(ev.event_date)


def _blurb(ev: EventModel) -> str:
    td = ev.theatrical_details if isinstance(ev.theatrical_details, dict) else {}
    syn = (td.get("synopsis") or "").strip()
    if syn:
        return syn[:280]
    return (ev.description or "")[:280]


class CampaignUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def _load_events(self, event_ids: list[UUID]) -> list[EventModel]:
        if not event_ids:
            return []
        result = await self._session.execute(select(EventModel).where(EventModel.id.in_(event_ids)))
        by_id = {e.id: e for e in result.scalars().all()}
        return [by_id[i] for i in event_ids if i in by_id]

    def _event_payload(self, events: list[EventModel]) -> list[dict]:
        return [
            {
                "id": str(e.id),
                "name": e.name,
                "when": _format_when(e),
                "city": e.city,
                "address": e.address,
                "image_url": e.main_image_url,
                "blurb": _blurb(e),
            }
            for e in events
        ]

    async def audience_users(self, audience: str, event_ids: list[UUID]) -> list[UserModel]:
        if audience not in VALID_AUDIENCES:
            audience = "opt_in"
        q = select(UserModel).where(
            UserModel.is_active.is_(True),
            UserModel.email_verified.is_(True),
            UserModel.marketing_opt_in.is_(True),
        )
        if audience == "opt_in_buyers":
            from tava.infrastructure.persistence.models import OrderModel
            from tava.domain.enums import PaymentStatus

            q = (
                q.join(OrderModel, OrderModel.buyer_id == UserModel.id)
                .where(OrderModel.payment_status == PaymentStatus.PAID)
                .distinct()
            )
        elif audience == "opt_in_favorites" and event_ids:
            from tava.infrastructure.persistence.models import FavoriteModel

            q = (
                q.join(FavoriteModel, FavoriteModel.user_id == UserModel.id)
                .where(FavoriteModel.event_id.in_(event_ids))
                .distinct()
            )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def count_audience(self, audience: str, event_ids: list[UUID] | None = None) -> int:
        users = await self.audience_users(audience, event_ids or [])
        return len(users)

    async def preview(
        self,
        *,
        format: str,
        subject: str,
        intro: str,
        event_ids: list[UUID],
    ) -> dict:
        if format not in VALID_FORMATS:
            raise ValueError("Formato inválido. Usa magazine o spotlight.")
        events = await self._load_events(event_ids)
        if not events:
            raise ValueError("Selecciona al menos un evento publicado.")
        if format == "spotlight":
            events = events[:1]
        payload = self._event_payload(events)
        html, text = build_promo_html(format=format, subject=subject, intro=intro, events=payload)
        return {"html": html, "text": text, "event_count": len(events)}

    async def create_campaign(
        self,
        *,
        admin_id: UUID,
        format: str,
        subject: str,
        intro: str,
        event_ids: list[UUID],
        audience: str,
    ) -> PromoCampaignModel:
        if format not in VALID_FORMATS:
            raise ValueError("Formato inválido. Usa magazine o spotlight.")
        if audience not in VALID_AUDIENCES:
            raise ValueError("Audiencia inválida.")
        subject = (subject or "").strip()
        if not subject:
            raise ValueError("El asunto es obligatorio.")
        events = await self._load_events(event_ids)
        if not events:
            raise ValueError("Selecciona al menos un evento.")
        # Solo publicados / visibles en cartelera preferible
        published = [e for e in events if e.status == EventStatus.PUBLISHED or e.cartelera_visible]
        if not published:
            published = events
        if format == "spotlight":
            published = published[:1]
        ids = [e.id for e in published]

        recipients = await self.audience_users(audience, ids)
        if not recipients:
            raise ValueError("No hay destinatarios con publicidad aceptada para esa audiencia.")

        campaign = PromoCampaignModel(
            created_by=admin_id,
            subject=subject[:200],
            intro_text=(intro or "").strip(),
            format=format,
            audience=audience,
            event_ids=[str(i) for i in ids],
            status="queued",
            total_recipients=len(recipients),
        )
        self._session.add(campaign)
        await self._session.flush()
        for user in recipients:
            self._session.add(
                PromoCampaignRecipientModel(
                    campaign_id=campaign.id,
                    user_id=user.id,
                    email=user.email,
                    status="pending",
                )
            )
        await self._session.flush()
        return campaign

    async def list_campaigns(self, limit: int = 20) -> list[PromoCampaignModel]:
        result = await self._session.execute(
            select(PromoCampaignModel).order_by(PromoCampaignModel.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def process_batch(self, limit: int = BATCH_SIZE) -> dict:
        """Envía hasta `limit` correos pendientes. Llamar desde el worker."""
        result = await self._session.execute(
            select(PromoCampaignRecipientModel)
            .options(selectinload(PromoCampaignRecipientModel.campaign))
            .where(PromoCampaignRecipientModel.status == "pending")
            .order_by(PromoCampaignRecipientModel.campaign_id, PromoCampaignRecipientModel.id)
            .limit(limit)
        )
        rows = list(result.scalars().all())
        if not rows:
            return {"sent": 0, "failed": 0}

        # Agrupar por campaña para reutilizar HTML
        by_campaign: dict[UUID, list[PromoCampaignRecipientModel]] = {}
        for row in rows:
            by_campaign.setdefault(row.campaign_id, []).append(row)

        sent = 0
        failed = 0
        now = datetime.now(UTC)

        for campaign_id, recipients in by_campaign.items():
            campaign = recipients[0].campaign
            if campaign.status == "queued":
                campaign.status = "sending"
                campaign.started_at = now
            event_uuids = [UUID(x) for x in (campaign.event_ids or [])]
            events = await self._load_events(event_uuids)
            if campaign.format == "spotlight" and events:
                events = events[:1]
            payload = self._event_payload(events)
            html, text = build_promo_html(
                format=campaign.format,
                subject=campaign.subject,
                intro=campaign.intro_text,
                events=payload,
            )
            for row in recipients:
                ok = await send_promo_email(row.email, campaign.subject, html, text)
                if ok:
                    row.status = "sent"
                    row.sent_at = now
                    campaign.sent_count = int(campaign.sent_count or 0) + 1
                    sent += 1
                else:
                    row.status = "failed"
                    row.error = "No se pudo enviar (Brevo/cupo/configuración)"
                    campaign.failed_count = int(campaign.failed_count or 0) + 1
                    failed += 1

            pending_left = await self._session.scalar(
                select(func.count())
                .select_from(PromoCampaignRecipientModel)
                .where(
                    PromoCampaignRecipientModel.campaign_id == campaign_id,
                    PromoCampaignRecipientModel.status == "pending",
                )
            )
            if not pending_left:
                campaign.status = "done"
                campaign.finished_at = now

        return {"sent": sent, "failed": failed}
