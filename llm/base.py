from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class ChatMessage(TypedDict):
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMBackend(ABC):
    """Общий интерфейс для любого LLM-бэкенда (локального или облачного)."""

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.9) -> str:
        """Вернуть текст ответа модели на список сообщений."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Вернуть эмбеддинг текста для RAG-поиска по дневнику."""
