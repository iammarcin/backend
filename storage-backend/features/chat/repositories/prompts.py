"""Repository helpers for saved prompts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from features.chat.db_models import Prompt
from features.chat.mappers import prompt_to_dict


class PromptRepository:
    """CRUD helpers for saved prompts."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_prompts(self, *, customer_id: int) -> list[dict[str, object]]:
        query = select(Prompt).where(Prompt.customer_id == customer_id).order_by(
            Prompt.prompt_id.asc()
        )
        result = await self._session.execute(query)
        return [prompt_to_dict(prompt) for prompt in result.scalars().all()]

    async def add_prompt(
        self,
        *,
        customer_id: int,
        title: str,
        prompt_text: str,
    ) -> Prompt:
        prompt = Prompt(customer_id=customer_id, title=title, prompt=prompt_text)
        self._session.add(prompt)
        await self._session.flush()
        return prompt

    async def update_prompt(
        self,
        *,
        prompt_id: int,
        title: str | None = None,
        prompt_text: str | None = None,
    ) -> Prompt:
        query = select(Prompt).where(Prompt.prompt_id == prompt_id)
        result = await self._session.execute(query)
        prompt = result.scalars().first()
        if prompt is None:
            raise DatabaseError("Prompt not found", operation="update_prompt")
        if title is not None:
            prompt.title = title
        if prompt_text is not None:
            prompt.prompt = prompt_text
        await self._session.flush()
        return prompt

    async def delete_prompt(self, *, prompt_id: int) -> bool:
        query = select(Prompt).where(Prompt.prompt_id == prompt_id)
        result = await self._session.execute(query)
        prompt = result.scalars().first()
        if prompt is None:
            return False
        await self._session.delete(prompt)
        await self._session.flush()
        return True


__all__ = ["PromptRepository"]

