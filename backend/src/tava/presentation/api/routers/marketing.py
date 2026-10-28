from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.campaigns import CampaignUseCase
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import BannerModel, EventModel, UserModel
from tava.domain.enums import EventStatus
from tava.presentation.api.platform_auth import require_platform_admin
from sqlalchemy import select

router = APIRouter(prefix="/marketing", tags=["Marketing"])


class CampaignBody(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    intro: str = ""
    format: str = Field(description="magazine | spotlight")
    audience: str = "opt_in"
    event_ids: list[UUID] = Field(min_length=1)
    custom_emails: list[str] = []


@router.get("/banners")
async def list_banners(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BannerModel).where(BannerModel.is_active.is_(True)).order_by(BannerModel.sort_order)
    )
    banners = result.scalars().all()
    return [
        {"id": str(b.id), "title": b.title, "image_url": b.image_url, "link_url": b.link_url, "type": b.banner_type}
        for b in banners
    ]


@router.get("/carousel/destacados")
async def featured_events(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EventModel)
        .where(EventModel.status == EventStatus.PUBLISHED)
        .order_by(EventModel.event_date.asc())
        .limit(8)
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "event_date": e.event_date.isoformat(),
            "main_image_url": e.main_image_url,
            "category": e.category,
        }
        for e in events
    ]


@router.get("/campaigns/audience-count")
async def audience_count(
    audience: str = "opt_in",
    db: AsyncSession = Depends(get_db),
    _admin: UserModel = Depends(require_platform_admin),
):
    count = await CampaignUseCase(db).count_audience(audience, [])
    return {"audience": audience, "count": count}


@router.post("/campaigns/preview")
async def preview_campaign(
    body: CampaignBody,
    db: AsyncSession = Depends(get_db),
    _admin: UserModel = Depends(require_platform_admin),
):
    try:
        return await CampaignUseCase(db).preview(
            format=body.format,
            subject=body.subject,
            intro=body.intro,
            event_ids=body.event_ids,
            direct=body.audience == "custom",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/campaigns")
async def create_campaign(
    body: CampaignBody,
    db: AsyncSession = Depends(get_db),
    admin: UserModel = Depends(require_platform_admin),
):
    uc = CampaignUseCase(db)
    try:
        campaign = await uc.create_campaign(
            admin_id=admin.id,
            format=body.format,
            subject=body.subject,
            intro=body.intro,
            event_ids=body.event_ids,
            audience=body.audience,
            custom_emails=body.custom_emails,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return {
        "id": str(campaign.id),
        "status": campaign.status,
        "total_recipients": campaign.total_recipients,
        "message": (
            f"Campaña en cola para {campaign.total_recipients} persona(s). "
            "Se enviará por lotes (máx. ~25 por minuto) respetando el cupo de Brevo."
        ),
    }


@router.get("/campaigns")
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    _admin: UserModel = Depends(require_platform_admin),
):
    rows = await CampaignUseCase(db).list_campaigns()
    return [
        {
            "id": str(c.id),
            "subject": c.subject,
            "format": c.format,
            "audience": c.audience,
            "status": c.status,
            "total_recipients": c.total_recipients,
            "sent_count": c.sent_count,
            "failed_count": c.failed_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]
