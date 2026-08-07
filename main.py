"""
main.py - точка входа kuni-lite
"""
import asyncio
import logging
import sys
from pathlib import Path

from config import Config
from telegram_client import TelegramUserbot
from llm.router import LLMRouter
from memory.diary import Diary
from memory.working_memory import WorkingMemory
from tts.piper_tts import PiperTTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("kuni-lite.main")


class KuniBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.llm_router = LLMRouter(cfg)
        self.diary = Diary(cfg.get("memory.diary_db_path", "./data/diary.db"))
        self.working_memory = WorkingMemory(cfg.get("memory.working_memory_path", "./data/working_memory.md"))
        self.tts = PiperTTS(
            voice_model_path=cfg.get("tts.voice_model_path", "./tts/voices/ru_RU-irina-medium.onnx"),
            enabled=cfg.get("tts.enabled", True)
        )
        self.telegram = TelegramUserbot(cfg, self._on_message)
    
    async def _on_message(self, chat_id: int, sender_id: int, text: str):
        """Обработчик входящих сообщений от Telegram."""
        logger.info(f"Новое сообщение от {sender_id} в чате {chat_id}: {text}")
        
        try:
            backend = self.llm_router.current()
            memories = await self.diary.recall(backend, text, top_k=6)
            system_prompt = self._build_system_prompt(memories)
            
            logger.info("Отправляем запрос в LLM...")
            response = await asyncio.to_thread(backend.chat, system_prompt, text)
            
            logger.info("Сохраняем в дневник...")
            embedding = await asyncio.to_thread(backend.embed, text)
            self.diary.add(chat_id, text, embedding)
            
            if self.tts.enabled and len(response) < 300:
                logger.info("Генерируем голосовой ответ...")
                ogg_path = await self.tts.synthesize(response)
                if ogg_path:
                    await self.telegram.send_voice(chat_id, ogg_path, duration=5)
            else:
                await self.telegram.send_text(chat_id, response)
            
            logger.info(f"Ответ отправлен: {response[:100]}...")
            
        except Exception as e:
            logger.exception(f"Ошибка при обработке сообщения: {e}")
            await self.telegram.send_text(chat_id, f"Ошибка: {str(e)}")
    
    def _build_system_prompt(self, memories: list) -> str:
        """Строит системный промпт с учётом памяти."""
        base_prompt = f"Ты - {self.cfg.character_name}, персональный ассистент {self.cfg.owner_name}.\n"
        base_prompt += f"Текущая кратковременная память:\n{self.working_memory.get_content()}\n\n"
        
        if memories:
            memory_text = "\n".join([f"- {m.text}" for m in memories])
            base_prompt += f"Твои воспоминания по этой теме:\n{memory_text}\n\n"
        
        base_prompt += "Отвечай кратко и по делу, как в обычном чате."
        return base_prompt
    
    async def start(self):
        """Запускает бота."""
        logger.info("Запуск KuniBot...")
        await self.telegram.start()
        logger.info("KuniBot успешно запущен!")
        
        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Остановка по сигналу...")
            await self.telegram.stop()


if __name__ == "__main__":
    cfg = Config.load("config.toml")
    bot = KuniBot(cfg)
    asyncio.run(bot.start())
