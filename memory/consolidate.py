from __future__ import annotations

import time

from llm.base import ChatMessage, LLMBackend

from .diary import Diary

CONSOLIDATE_PROMPT = """Вот несколько связанных записей из твоего дневника
(похожие по смыслу или по времени). Объедини их в одну или несколько более
коротких записей:
- слей повторяющиеся/похожие воспоминания в одно
- сохрани важные эмоциональные и фактические детали
- отбрось незначительные и дублирующиеся детали
- если записи не связаны между собой по смыслу — верни их как отдельные строки, не выдумывай связи

Записи:
{entries}

Верни только итоговый список записей, каждая на отдельной строке, без нумерации и пояснений.
"""


async def run_consolidation(
    diary: Diary,
    backend: LLMBackend,
    *,
    max_seconds: int = 30 * 60,
    chunk_size: int = 8,
) -> int:
    """Ночная 'консолидация памяти' — аналог сна у Kuni. Возвращает число
    обработанных записей. Останавливается либо когда дневник кончился, либо
    по истечении max_seconds (чтобы не съесть весь CPU-бюджет ночи)."""
    started = time.time()
    processed = 0

    while time.time() - started < max_seconds:
        chunk = diary.oldest_first_chunk(chunk_size)
        if len(chunk) < 2:
            break  # нечего сливать

        entries_text = "\n".join(f"- {e.text}" for e in chunk)
        messages: list[ChatMessage] = [
            {"role": "user", "content": CONSOLIDATE_PROMPT.format(entries=entries_text)}
        ]
        result = await backend.chat(messages, temperature=0.4)
        new_lines = [line.strip("- ").strip() for line in result.splitlines() if line.strip()]

        chat_id = chunk[0].chat_id
        old_ids = [e.id for e in chunk]
        diary.delete(old_ids)
        for line in new_lines:
            embedding = await backend.embed(line)
            diary.add(chat_id, line, embedding)

        processed += len(chunk)

    return processed
