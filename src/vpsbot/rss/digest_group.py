from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpsbot.db.models import DigestGroupState


async def get_digest_group_enabled(session: AsyncSession, group_chat_id: int) -> bool:
    row = await session.get(DigestGroupState, group_chat_id)
    return bool(row and row.enabled)


async def set_digest_group_enabled(
    session: AsyncSession,
    group_chat_id: int,
    enabled: bool,
    updated_by: int,
) -> None:
    row = await session.get(DigestGroupState, group_chat_id)
    if row is None:
        row = DigestGroupState(
            group_chat_id=group_chat_id,
            enabled=enabled,
            updated_by=updated_by,
        )
        session.add(row)
    else:
        row.enabled = enabled
        row.updated_by = updated_by
    await session.commit()


async def any_digest_group_enabled(
    session: AsyncSession,
    group_chat_id: int,
) -> bool:
    result = await session.execute(
        select(DigestGroupState).where(
            DigestGroupState.group_chat_id == group_chat_id,
            DigestGroupState.enabled.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None
