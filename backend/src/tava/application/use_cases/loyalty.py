from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.infrastructure.persistence.models import CollectibleModel, LoyaltyRewardModel


LOYALTY_EVENTS_REQUIRED = 5


class LoyaltyUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def grant_collectible(self, user_id: UUID, event_id: UUID, lamina_url: str) -> None:
        existing = await self._session.execute(
            select(CollectibleModel).where(
                CollectibleModel.user_id == user_id,
                CollectibleModel.event_id == event_id,
            )
        )
        if existing.scalar_one_or_none():
            return
        self._session.add(
            CollectibleModel(user_id=user_id, event_id=event_id, lamina_url=lamina_url)
        )
        await self._session.flush()
        await self._check_reward(user_id)

    async def _check_reward(self, user_id: UUID) -> None:
        count_result = await self._session.execute(
            select(func.count()).select_from(CollectibleModel).where(CollectibleModel.user_id == user_id)
        )
        count = count_result.scalar() or 0
        if count < LOYALTY_EVENTS_REQUIRED:
            return
        pending = await self._session.execute(
            select(LoyaltyRewardModel).where(
                LoyaltyRewardModel.user_id == user_id,
                LoyaltyRewardModel.redeemed.is_(False),
            )
        )
        if pending.scalar_one_or_none():
            return
        self._session.add(LoyaltyRewardModel(user_id=user_id, events_required=LOYALTY_EVENTS_REQUIRED))
        await self._session.flush()

    async def get_collection(self, user_id: UUID) -> dict:
        result = await self._session.execute(
            select(CollectibleModel).where(CollectibleModel.user_id == user_id).order_by(
                CollectibleModel.earned_at.desc()
            )
        )
        items = result.scalars().all()
        reward_result = await self._session.execute(
            select(LoyaltyRewardModel).where(
                LoyaltyRewardModel.user_id == user_id,
                LoyaltyRewardModel.redeemed.is_(False),
            )
        )
        reward = reward_result.scalar_one_or_none()
        return {
            "laminas": [
                {"event_id": str(c.event_id), "lamina_url": c.lamina_url, "earned_at": c.earned_at.isoformat()}
                for c in items
            ],
            "total": len(items),
            "progress_to_free_ticket": min(len(items), LOYALTY_EVENTS_REQUIRED),
            "events_required": LOYALTY_EVENTS_REQUIRED,
            "free_ticket_available": reward is not None,
        }
