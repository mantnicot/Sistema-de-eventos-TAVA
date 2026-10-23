from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.services import site_settings as site_svc
from tava.presentation.api.platform_auth import require_platform_admin

router = APIRouter(prefix="/settings", tags=["Configuración del sitio"])


class AppearancePublicResponse(BaseModel):
    loader_video_url: str
    loader_video_enabled: bool
    captcha_enabled: bool = False


class AppearanceUpdateRequest(BaseModel):
    loader_video_url: str = Field(max_length=500)
    loader_video_enabled: bool = True
    captcha_enabled: bool = False


class CheckoutFeesResponse(BaseModel):
    fee_percent: float
    fee_fixed_cop: float
    fee_iva: float
    rounding_step: int = 100


class CheckoutFeesUpdateRequest(BaseModel):
    fee_percent: float = Field(ge=0, le=0.2)
    fee_fixed_cop: float = Field(ge=0, le=20000)
    fee_iva: float = Field(ge=0, le=0.5)


@router.get("/appearance", response_model=AppearancePublicResponse)
async def get_appearance(db: AsyncSession = Depends(get_db)):
    data = await site_svc.get_public_appearance(db)
    return AppearancePublicResponse(**data)


@router.put("/appearance", response_model=AppearancePublicResponse)
async def update_appearance(
    body: AppearanceUpdateRequest,
    _user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    await site_svc.set_setting(db, site_svc.KEY_LOADER_VIDEO_URL, body.loader_video_url.strip())
    await site_svc.set_setting(
        db, site_svc.KEY_LOADER_VIDEO_ENABLED, "true" if body.loader_video_enabled else "false"
    )
    await site_svc.set_setting(
        db, site_svc.KEY_CAPTCHA_ENABLED, "true" if body.captcha_enabled else "false"
    )
    data = await site_svc.get_public_appearance(db)
    return AppearancePublicResponse(**data)


@router.get("/checkout-fees", response_model=CheckoutFeesResponse)
async def get_checkout_fees(db: AsyncSession = Depends(get_db)):
    return CheckoutFeesResponse(**await site_svc.get_checkout_fees(db))


@router.put("/checkout-fees", response_model=CheckoutFeesResponse)
async def update_checkout_fees(
    body: CheckoutFeesUpdateRequest,
    _user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await site_svc.set_checkout_fees(
        db,
        percent=body.fee_percent,
        fixed=body.fee_fixed_cop,
        iva=body.fee_iva,
    )
    return CheckoutFeesResponse(**data)
