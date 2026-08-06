from __future__ import annotations

import logging
import asyncio
import traceback
from threading import Lock

from aiotdlib import Client, ClientSettings, ClientProxySettings, ClientProxyType
from aiotdlib.api import API, UpdateNewMessage, UpdateAuthorizationState

from config import Config

logger = logging.getLogger("kuni-lite.telegram")


class TelegramUserbot:
    def __init__(self, cfg: Config, on_message):
        self.cfg = cfg
        self.on_message = on_message
        self.client: Client | None = None
        self._update_lock = Lock()  # Чтобы не плодить задачи

    async def start(self) -> None:
        proxy_host = self.cfg.get("telegram.proxy.host", "") or ""
        proxy_settings = None
        if proxy_host:
            proxy_settings = ClientProxySettings(
                host=proxy_host,
                port=int(self.cfg.get("telegram.proxy.port")),
                type=ClientProxyType.MTPROTO,
                secret=self.cfg.get("telegram.proxy.secret", ""),
            )
            logger.info(f"Используем MTProxy: {proxy_host}")

        settings = ClientSettings(
            api_id=self.cfg.get("telegram.api_id"),
            api_hash=self.cfg.get("telegram.api_hash"),
            phone_number=self.cfg.get("telegram.phone_number"),
            library_path=self.cfg.get("telegram.tdjson_path", None) or None,
            proxy_settings=proxy_settings,
            device_model="Redmi 13C",
            system_version="Android 14",
            application_version="12.9.0",
        )
        self.client = Client(settings=settings)

        # ========================================
        # ФИКС: ОБРАБОТЧИК ВСЕХ ОБНОВЛЕНИЙ
        # ========================================
        async def _handle_any(client: Client, update):
            """Ловит все обновления и фильтрует только нужные"""
            try:
                # Проверяем наличие ID
                if not hasattr(update, 'ID'):
                    logger.debug(f"Ignored update without ID: {type(update)}")
                    return
                
                update_id = update.ID
                
                # Пропускаем только нужные типы
                if update_id not in ['updatenewmessage', 'updateauthorizationstate']:
                    logger.debug(f"Ignored update: {update_id}")
                    return
                
                # Для нужных типов — передаём дальше
                if update_id == 'updateauthorizationstate':
                    await _handle_auth_state(client, update)
                elif update_id == 'updatenewmessage':
                    await _handle_new_message(client, update)
                    
            except Exception as e:
                logger.error(f"Update handler error: {e}")
                logger.debug(traceback.format_exc())

        async def _handle_auth_state(client: Client, update: UpdateAuthorizationState):
            state_type = update.authorization_state.ID
            logger.info(f"AUTH STATE: {state_type}")
            print(f"\n>>> Статус авторизации: {state_type}", flush=True)

            if state_type == "authorizationStateWaitCode":
                code = input(">>> Введи код авторизации Telegram: ").strip()
                await client.api.check_authentication_code(code=code)
            elif state_type == "authorizationStateWaitPassword":
                password = input(">>> Введи пароль двухфакторки: ").strip()
                await client.api.check_authentication_password(password=password)

        async def _handle_new_message(client: Client, update: UpdateNewMessage):
            message = update.message
            if message.is_outgoing:
                return

            chat_id = message.chat_id
            text = _extract_text(message)
            if not text:
                return

            sender_id = _extract_sender_id(message)
            
            # Запускаем в отдельную задачу, чтобы не блокировать клиент
            asyncio.create_task(self.on_message(chat_id=chat_id, sender_id=sender_id, text=text))

        # Регистрируем ОДИН обработчик на все обновления
        self.client.add_event_handler(_handle_any)

        await self.client.start()
        logger.info("Telegram userbot запущен")

    async def send_text(self, chat_id: int, text: str) -> None:
        await self.client.api.send_message(
            chat_id=chat_id,
            input_message_content=API.types.inputMessageText(
                text=API.types.formattedText(text=text, entities=[]),
            ),
        )

    async def send_voice(self, chat_id: int, ogg_path: str, duration: int) -> None:
        await self.client.api.send_message(
            chat_id=chat_id,
            input_message_content=API.types.inputMessageVoiceNote(
                voice_note=API.types.inputFileLocal(path=ogg_path),
                duration=duration,
            ),
        )

    async def mark_read(self, chat_id: int, message_id: int) -> None:
        await self.client.api.view_messages(chat_id=chat_id, message_ids=[message_id])

    async def stop(self) -> None:
        if self.client:
            await self.client.stop()


def _extract_text(message) -> str | None:
    content = message.content
    text_field = getattr(content, "text", None)
    if text_field is not None:
        return text_field.text
    return None


def _extract_sender_id(message) -> int:
    sender = message.sender_id
    return getattr(sender, "user_id", 0)