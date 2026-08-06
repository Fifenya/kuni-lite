from __future__ import annotations

import httpx

from .base import ChatMessage, LLMBackend


class ApiBackend(LLMBackend):
    """Облачный OpenAI-совместимый эндпоинт (DeepSeek и т.п.). Быстрее и умнее
    локальной модели, не грузит слабый CPU сервера, но стоит денег и требует интернет.

    Эмбеддинги для дневника всё равно считаются через отдельный (обычно локальный
    Ollama) эндпоинт — они маленькие, гонять их в облако смысла нет.
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 embedding_host: str, embedding_model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_host = embedding_host.rstrip("/")
        self.embedding_model = embedding_model
        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._embed_client = httpx.AsyncClient(timeout=60.0)

    async def chat(self, messages: list[ChatMessage], *, temperature: float = 0.9) -> str:
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        resp = await self._embed_client.post(
            f"{self.embedding_host}/api/embeddings",
            json={"model": self.embedding_model, "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
