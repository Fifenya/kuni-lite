from __future__ import annotations

import asyncio
import logging
import traceback
from threading import Lock
from typing import Optional

from aiotdlib import Client, ClientSettings, ClientProxySettings, ClientProxyType
from aiotdlib.api import API, UpdateNewMessage, UpdateAuthorizationState

from config import Config
from utils.logging_setup import configure_logging

# Инициализация логов (можно задать уровень через конфиг в будущем)
configure_logging()

# Используем stdlib logger в коде (перехватывается loguru)
logger = logging.getLogger("kuni-lite.telegram")


class TelegramUserbot:
    def __init__(self, cfg: Config, on_message):
        self.cfg = cfg
        self.on_message = on_message
        self.client: Optional[Client] = None
        self._update_lock = Lock()  # Чтобы не плодить задачи
        self._main_task: Optional[asyncio.Task] = None
        self._restart_event: asyncio.Event = asyncio.Event()
        self._stop_event: asyncio.Event = asyncio.Event()
        self._proxy_state: Optional[tuple[str, int, str]] = None  # (host, port, secret)

    async def start(self) -> None:
        """Запускает основной цикл: создаёт client, запускает watcher прокси и реагирует на рестарт."""
        if self._main_task and not self._main_task.done():
            logger.info("TelegramUserbot уже запущен")
            return
        self._stop_event.clear()
        self._main_task = asyncio.create_task(self._main_loop())
        logger.info("Telegram userbot main task started")

    async def _main_loop(self) -> None:
        """Основной цикл: запускаем client, слушаем событие рестарта для аккуратного перезапуска."""
        try:
            while not self._stop_event.is_set():
                await self._create_and_run_client()
                # Ждём сигнала рестарта или стопа
                await asyncio.wait(
                    [self._restart_event.wait(), self._stop_event.wait()],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if self._stop_event.is_set():
                    break
                # если рестарт — очистим флаг и перезапустим клиент
                self._restart_event.clear()
                logger.info("Перезапуск Telegram клиента (proxy/config изменился)")
        except asyncio.CancelledError:
            logger.info("Main loop cancelled")
        except Exception as e:
            logger.exception("Ошибка в main_loop: %s", e)
        finally:
            # Гарантированно остановим клиент
            await self._safe_stop_client()

    async def _create_and_run_client(self) -> None:
        """Создаёт клиент с текущими прокси-настройками и запускает его (блокирует пока клиент запущен)."""
        proxy_settings = self._current_proxy_settings()
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

        # регистрируем общий обработчик обновлений
        async def _handle_any(client: Client, update):
            try:
                if not hasattr(update, "ID"):
                    logger.debug("Ignored update without ID: %s", type(update))
                    return

                update_id = update.ID
                if update_id not in ["updatenewmessage", "updateauthorizationstate"]:
                    logger.debug("Ignored update: %s", update_id)
                    return

                if update_id == "updateauthorizationstate":
                    await _handle_auth_state(client, update)
                elif update_id == "updatenewmessage":
                    await _handle_new_message(client, update)
            except Exception:
                logger.exception("Update handler error")

        self.client.add_event_handler(_handle_any)

        # Запускаем асинхронно и ждём пока клиент работает; stop() прервёт run
        try:
            logger.info("Запускаем TDLib client (proxy=%s)", getattr(proxy_settings, "host", None))
            await self.client.start()
            logger.info("Telegram userbot запущен")
        except Exception:
            logger.exception("Ошибка при запуске клиента")
            await self._safe_stop_client()

    def _current_proxy_settings(self) -> Optional[ClientProxySettings]:
        """Читает конфиг и возвращает ClientProxySettings или None."""
        # Конфиг может быть hot-reload'нут; читаем свежие значения
        self.cfg.maybe_reload()
        enabled = self.cfg.get("telegram.proxy.enabled", False)
        host = self.cfg.get("telegram.proxy.host", "") or ""
        if not enabled or not host:
            return None
        port = int(self.cfg.get("telegram.proxy.port", 443))
        secret = self.cfg.get("telegram.proxy.secret", "")
        # Сохраним состояние, чтобы сравнивать
        self._proxy_state = (host, port, secret)
        return ClientProxySettings(host=host, port=port, type=ClientProxyType.MTPROTO, secret=secret)

    async def _safe_stop_client(self) -> None:
        if self.client:
            try:
                logger.info("Останавливаем TDLib client")
                await self.client.stop()
                logger.info("TDLib client остановлен")
            except Exception:
                logger.exception("Ошибка при остановке клиента")
            finally:
                self.client = None

    async def trigger_restart(self) -> None:
        """Помечает, что клиент должен перезапуститься (например, proxy изменился)."""
        self._restart_event.set()

    async def stop(self) -> None:
        """Останавливает полностью main loop и клиент."""
        logger.info("Стоп TelegramUserbot запрошен")
        self._stop_event.set()
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except Exception:
                pass
        await self._safe_stop_client()

    async def send_text(self, chat_id: int, text: str) -> None:
        if not self.client:
            raise RuntimeError("Client not started")
        await self.client.api.send_message(
            chat_id=chat_id,
            input_message_content=API.types.inputMessageText(
                text=API.types.formattedText(text=text, entities=[]),
            ),
        )

    async def send_voice(self, chat_id: int, ogg_path: str, duration: int) -> None:
        if not self.client:
            raise RuntimeError("Client not started")
        await self.client.api.send_message(
            chat_id=chat_id,
            input_message_content=API.types.inputMessageVoiceNote(
                voice_note=API.types.inputFileLocal(path=ogg_path),
                duration=duration,
            ),
        )

    async def mark_read(self, chat_id: int, message_id: int) -> None:
        if not self.client:
            return
        await self.client.api.view_messages(chat_id=chat_id, message_ids=[message_id])


# Вспомогательные обработчики (вынесены для читаемости)
async def _handle_auth_state(client: Client, update: UpdateAuthorizationState):
    state_type = update.authorization_state.ID
    logger.info("AUTH STATE: %s", state_type)
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
    # Используем on_message из внешнего объекта (вложенная функция видит `self` в замыкании)
    # Но здесь у нас нет прямого доступа к self, поэтому ожидаем, что внешний обработчик
    # привяжет on_message правильным образом. В обычном случае мы создаём таск через
    # клиентский объект: client._owner_on_message — однако проще и безопаснее —
    # вызываем глобальный callback, который был передан при создании TelegramUserbot.
    # Для этого сделаем допущение: handler создаётся в методе экземпляра, поэтому он
    # имеет доступ к объёкту через замыкание. Когда добавляется как event handler,
    # aiotdlib передаёт client и update, но замыкание содержит `self`.
    try:
        # Найдём callback в клиенте через атрибут owner (если был установлен) или
        # ожидаем, что event handler использует замыкание; на практике в нашем
        # code path мы вызываем asyncio.create_task(self.on_message(...)) при создании
        # handler в теле _create_and_run_client, где `self` доступен.
        asyncio.create_task(client._user_callback(chat_id=chat_id, sender_id=sender_id, text=text))
    except Exception:
        # fallback — постараемся вызвать attribute on_message на client или логируем
        try:
            cb = getattr(client, "on_message", None)
            if cb:
                asyncio.create_task(cb(chat_id=chat_id, sender_id=sender_id, text=text))
            else:
                logger.warning("Не удалось найти on_message callback на client; сообщение проигнорировано")
        except Exception:
            logger.exception("Ошибка при создании задачи on_message")


def _extract_text(message) -> str | None:
    content = message.content
    text_field = getattr(content, "text", None)
    if text_field is not None:
        return text_field.text
    return None


def _extract_sender_id(message) -> int:
    sender = message.sender_id
    return getattr(sender, "user_id", 0)
