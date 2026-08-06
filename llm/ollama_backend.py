from __future__ import annotations

import httpx

from .base import ChatMessage, LLMBackend


class OllamaBackend(LLMBackend):
    """Локальный CPU-инференс через Ollama. Медленнее и слабее облака,
    но бесплатно и не требует интернета."""

    def __init__(self, host: str, model: str, embedding_model: str):
        self.host = host.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self._client = httpx.AsyncClient(timeout=180.0)  # CPU-инференс медленный, таймаут щедрый

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.9) -> str:
        resp = await self._client.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        resp = await self._client.post(
            f"{self.host}/api/embeddings",
            json={"model": self.embedding_model, "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
