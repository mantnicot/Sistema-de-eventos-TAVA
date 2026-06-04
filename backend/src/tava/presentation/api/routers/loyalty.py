from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.loyalty import LoyaltyUseCase
from tava.infrastructure.persistence.database import get_db
from tava.presentation.api.dependencies import get_current_user

router = APIRouter(prefix="/loyalty", tags=["Fidelización — Coleccionables TAVA"])


@router.get("/collection")
async def my_collection(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    uc = LoyaltyUseCase(db)
    return await uc.get_collection(user.id)
