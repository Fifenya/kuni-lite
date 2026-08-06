from __future__ import annotations

from config import Config

from .api_backend import ApiBackend
from .base import LLMBackend
from .ollama_backend import OllamaBackend


class LLMRouter:
    """Отдаёт актуальный бэкенд по значению config.llm.llm_backend.
    Конфиг hot-reload'ится, так что переключение ollama <-> api происходит
    без перезапуска процесса (подхватится на следующем сообщении)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._backends: dict[str, LLMBackend] = {}

    def _build(self, name: str) -> LLMBackend:
        if name == "ollama":
            return OllamaBackend(
                host=self.cfg.get("llm.ollama.host", "http://localhost:11434"),
                model=self.cfg.get("llm.ollama.model", "qwen3.5:9b"),
                embedding_model=self.cfg.get("llm.ollama.embedding_model", "qwen3-embedding"),
            )
        if name == "api":
            return ApiBackend(
                base_url=self.cfg.get("llm.api.base_url", ""),
                api_key=self.cfg.get("llm.api.api_key", ""),
                model=self.cfg.get("llm.api.model", ""),
                embedding_host=self.cfg.get("llm.api.embedding_host", "http://localhost:11434"),
                embedding_model=self.cfg.get("llm.api.embedding_model", "qwen3-embedding"),
            )
        raise ValueError(f"Unknown llm_backend: {name}")

    def current(self) -> LLMBackend:
        self.cfg.maybe_reload()
        name = self.cfg.llm_backend
        if name not in self._backends:
            self._backends[name] = self._build(name)
        return self._backends[name]
