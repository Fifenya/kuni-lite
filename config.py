from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class Config:
    path: Path
    _raw: dict = field(default_factory=dict)
    _mtime: float = 0.0

    @classmethod
    def load(cls, path: str = "config.toml") -> "Config":
        cfg = cls(path=Path(path))
        cfg._reload()
        return cfg

    def _reload(self) -> None:
        with open(self.path, "rb") as f:
            self._raw = tomllib.load(f)
        self._mtime = self.path.stat().st_mtime

    def maybe_reload(self) -> None:
        """Hot-reload: call periodically (e.g. before building each response)."""
        try:
            if self.path.stat().st_mtime != self._mtime:
                self._reload()
        except FileNotFoundError:
            pass

    def get(self, dotted_key: str, default=None):
        node = self._raw
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    # convenience shortcuts used throughout the codebase
    @property
    def character_name(self) -> str:
        return self.get("general.character_name", "Kuni")

    @property
    def owner_chat_id(self) -> int:
        return self.get("general.owner_chat_id", 0)

    @property
    def llm_backend(self) -> str:
        return self.get("llm.llm_backend", "ollama")
