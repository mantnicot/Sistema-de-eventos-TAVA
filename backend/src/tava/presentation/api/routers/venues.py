from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from tava.infrastructure.persistence.database import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import SeatStatus, UserRole
from tava.infrastructure.persistence.models import SeatModel, SectorModel, VenueModel
from tava.presentation.api.dependencies import require_roles
from tava.presentation.api.schemas import SectorCreateRequest, VenueCreateRequest

router = APIRouter(prefix="/venues", tags=["Escenarios y Silletería"])


@router.post("")
async def create_venue(
    body: VenueCreateRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    venue = VenueModel(**body.model_dump())
    db.add(venue)
    await db.flush()
    await db.refresh(venue)
    return {"id": str(venue.id), "name": venue.name, "venue_type": venue.venue_type.value}


@router.post("/{venue_id}/sectors")
async def create_sector_with_seats(
    venue_id: UUID,
    body: SectorCreateRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VenueModel).where(VenueModel.id == venue_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    sector = SectorModel(
        venue_id=venue_id,
        name=body.name,
        color=body.color,
        price_multiplier=body.price_multiplier,
    )
    db.add(sector)
    await db.flush()
    seats = []
    for r in range(1, body.rows + 1):
        for c in range(1, body.cols + 1):
            seats.append(
                SeatModel(
                    sector_id=sector.id,
                    row_label=str(r),
                    col_label=chr(64 + c) if c <= 26 else str(c),
                    status=SeatStatus.AVAILABLE,
                )
            )
    db.add_all(seats)
    await db.flush()
    return {
        "sector_id": str(sector.id),
        "seats_created": len(seats),
        "name": sector.name,
    }


@router.get("/{venue_id}/map")
async def get_seat_map(venue_id: UUID, db: AsyncSession = Depends(get_db)):
    sectors_result = await db.execute(select(SectorModel).where(SectorModel.venue_id == venue_id))
    sectors = sectors_result.scalars().all()
    data = []
    for sector in sectors:
        seats_result = await db.execute(select(SeatModel).where(SeatModel.sector_id == sector.id))
        seats = seats_result.scalars().all()
        data.append(
            {
                "id": str(sector.id),
                "name": sector.name,
                "color": sector.color,
                "seats": [
                    {
                        "id": str(s.id),
                        "row": s.row_label,
                        "col": s.col_label,
                        "status": s.status.value,
                    }
                    for s in seats
                ],
            }
        )
    return data
