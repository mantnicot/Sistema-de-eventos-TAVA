from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.services import site_settings as site_svc
from tava.presentation.api.dependencies import require_roles

router = APIRouter(prefix="/settings", tags=["Configuración del sitio"])


class AppearancePublicResponse(BaseModel):
    hero_video_url: str
    hero_video_enabled: bool


class AppearanceUpdateRequest(BaseModel):
    hero_video_url: str = Field(max_length=500)
    hero_video_enabled: bool = True


@router.get("/appearance", response_model=AppearancePublicResponse)
async def get_appearance(db: AsyncSession = Depends(get_db)):
    data = await site_svc.get_public_appearance(db)
    return AppearancePublicResponse(**data)


@router.put("/appearance", response_model=AppearancePublicResponse)
async def update_appearance(
    body: AppearanceUpdateRequest,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await site_svc.set_setting(db, site_svc.KEY_HERO_VIDEO_URL, body.hero_video_url.strip())
    await site_svc.set_setting(
        db, site_svc.KEY_HERO_VIDEO_ENABLED, "true" if body.hero_video_enabled else "false"
    )
    data = await site_svc.get_public_appearance(db)
    return AppearancePublicResponse(**data)
