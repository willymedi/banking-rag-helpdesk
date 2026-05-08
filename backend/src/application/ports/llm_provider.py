from typing import AsyncIterator, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ) -> T: ...

    async def stream_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "gpt-4o",
        temperature: float = 0.2,
    ) -> AsyncIterator[str]: ...

    async def classify_attack(self, text: str) -> tuple[bool, str, float]:
        """Returns (is_attack, attack_type, confidence)."""
        ...
