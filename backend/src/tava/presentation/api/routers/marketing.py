from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import BannerModel, EventModel
from tava.domain.enums import EventStatus

router = APIRouter(prefix="/marketing", tags=["Marketing"])


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
