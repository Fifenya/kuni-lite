"""
Универсальный LLM-клиент для Telegram Userbot
"""

import logging
from openai import OpenAI

logger = logging.getLogger("kuni-lite.llm")


class LLMClient:
    def __init__(self, config: dict):
        self.provider = config.get("provider", "groq")
        self.model = config.get("model")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 1024)
        
        self.client = OpenAI(
            base_url=config.get("base_url"),
            api_key=config.get("api_key"),
            timeout=config.get("timeout", 60.0)
        )
        
        logger.info(f"LLM готов: {self.provider}/{self.model}")

    def generate(self, user_text: str, system_prompt: str = "Ты — полезный ассистент.") -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM ошибка: {e}")
            return "⚠️ Ошибка генерации. Попробуй позже."