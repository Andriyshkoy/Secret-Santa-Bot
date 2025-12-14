import random
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Participant


class RegistrationClosedError(Exception):
    pass


class AlreadyRegisteredError(Exception):
    pass


class NotRegisteredError(Exception):
    pass


class ShuffleError(Exception):
    pass


class NotShuffledError(Exception):
    pass


class AlreadyShuffledError(ShuffleError):
    pass


class CannotLeaveAfterShuffleError(Exception):
    pass


class ParticipantService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> Optional[Participant]:
        result = await self.session.execute(select(Participant).where(Participant.tg_id == tg_id))
        return result.scalar_one_or_none()

    async def is_shuffle_completed(self) -> bool:
        result = await self.session.execute(
            select(
                func.count(Participant.id),
                func.count(Participant.assigned_to_id),
            )
        )
        total, assigned = result.one()
        return total > 0 and assigned == total

    async def register(
        self, *, tg_id: int, username: str | None, first_name: str | None, display_name: str
    ) -> Participant:
        if await self.is_shuffle_completed():
            raise RegistrationClosedError("Shuffle already finished, registration is closed.")

        existing = await self.get_by_tg_id(tg_id)
        if existing:
            raise AlreadyRegisteredError("You are already registered.")

        participant = Participant(
            tg_id=tg_id,
            username=username,
            first_name=first_name,
            display_name=display_name.strip() or (first_name or "Участник"),
        )
        self.session.add(participant)
        await self.session.flush()
        return participant

    async def update_wishes(self, tg_id: int, wishes: str) -> Participant:
        participant = await self.get_by_tg_id(tg_id)
        if not participant:
            raise NotRegisteredError("You are not registered.")

        participant.wishes = wishes.strip()
        await self.session.flush()
        return participant

    async def update_name(self, tg_id: int, display_name: str) -> Participant:
        participant = await self.get_by_tg_id(tg_id)
        if not participant:
            raise NotRegisteredError("You are not registered.")

        participant.display_name = display_name.strip() or (participant.first_name or "Участник")
        await self.session.flush()
        return participant

    async def unregister(self, tg_id: int) -> None:
        if await self.is_shuffle_completed():
            raise CannotLeaveAfterShuffleError("Cannot leave after shuffle.")

        participant = await self.get_by_tg_id(tg_id)
        if not participant:
            raise NotRegisteredError("You are not registered.")

        await self.session.delete(participant)
        await self.session.flush()

    async def shuffle(self) -> List[tuple[Participant, Participant]]:
        if await self.is_shuffle_completed():
            raise AlreadyShuffledError("Shuffle already completed.")

        participants = (await self.session.execute(select(Participant))).scalars().all()
        if len(participants) < 2:
            raise ShuffleError("Need at least two participants to shuffle.")

        order = participants[:]
        random.shuffle(order)

        pairs: List[tuple[Participant, Participant]] = []
        for idx, santa in enumerate(order):
            recipient = order[(idx + 1) % len(order)]
            santa.assigned_to_id = recipient.id
            pairs.append((santa, recipient))

        await self.session.flush()
        return pairs

    async def get_recipient_for(self, tg_id: int) -> Participant:
        participant = await self.get_by_tg_id(tg_id)
        if not participant:
            raise NotRegisteredError("You are not registered.")
        if not participant.assigned_to_id:
            raise NotShuffledError("Shuffle is not finished yet.")

        recipient = await self.session.get(Participant, participant.assigned_to_id)
        if not recipient:
            raise NotShuffledError("Shuffle data looks broken.")
        return recipient

    async def find_santa_for(self, recipient_id: int) -> Optional[Participant]:
        result = await self.session.execute(
            select(Participant).where(Participant.assigned_to_id == recipient_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> List[Participant]:
        return (await self.session.execute(select(Participant))).scalars().all()
