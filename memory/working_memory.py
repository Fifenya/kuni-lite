from __future__ import annotations

from pathlib import Path

from llm.base import ChatMessage, LLMBackend

UPDATE_PROMPT = """Ты обновляешь свою "рабочую память" - короткий список дел,
обещаний и важных деталей на ближайшие 1-3 дня. Вот текущая рабочая память:

---
{current}
---

А вот свежий фрагмент разговора, который нужно учесть:
---
{recent_context}
---

Перепиши рабочую память заново по правилам:
- сохрани все незавершённые задачи/обещания/напоминания из старой версии
- убери то, что уже выполнено или устарело (старше ~3 дней)
- добавь новые важные детали из свежего разговора
- формат: короткий markdown-список с датами
- никаких пояснений от себя, только сам обновлённый список
"""


class WorkingMemory:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("(пока пусто)\n", encoding="utf-8")

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def write(self, content: str) -> None:
        self.path.write_text(content, encoding="utf-8")

    async def update_from_context(self, backend: LLMBackend, recent_context: str) -> None:
        prompt = UPDATE_PROMPT.format(current=self.read(), recent_context=recent_context)
        messages: list[ChatMessage] = [{"role": "user", "content": prompt}]
        new_content = await backend.chat(messages, temperature=0.3)
        self.write(new_content.strip() + "\n")
