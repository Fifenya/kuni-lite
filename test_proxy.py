#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Telegram через MTProto прокси.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from aiotdlib import Client, ClientSettings, ClientProxySettings, ClientProxyType


async def test_connection():
    print("=" * 60)
    print("Тест подключения к Telegram")
    print("=" * 60)
    
    try:
        cfg = Config.load("config.toml")
        print("[OK] config.toml загружен")
    except Exception as e:
        print(f"[ОШИБКА] Не удалось загрузить config.toml: {e}")
        return False
    
    api_id = cfg.get("telegram.api_id")
    api_hash = cfg.get("telegram.api_hash")
    phone_number = cfg.get("telegram.phone_number")
    tdjson_path = cfg.get("telegram.tdjson_path")
    
    if not api_id or not api_hash or not phone_number:
        print("[ОШИБКА] Не заполнены telegram.api_id, api_hash или phone_number")
        return False
    
    print(f"[OK] Telegram API ID: {api_id}")
    print(f"[OK] Phone number: {phone_number}")
    
    proxy_enabled = cfg.get("telegram.proxy.enabled", False)
    proxy_settings = None
    
    if proxy_enabled:
        host = cfg.get("telegram.proxy.host")
        port = cfg.get("telegram.proxy.port", 443)
        secret = cfg.get("telegram.proxy.secret")
        
        if host and secret:
            print(f"[OK] Прокси включён: {host}:{port}")
            print(f"[OK] Secret: {secret[:10]}...")
            proxy_settings = ClientProxySettings(
                host=host,
                port=int(port),
                type=ClientProxyType.MTPROTO,
                secret=secret
            )
        else:
            print("[ВНИМАНИЕ] Прокси включён, но host/secret не заполнены")
    else:
        print("[ВНИМАНИЕ] Прокси отключён! В РФ подключение может не работать.")
    
    if tdjson_path:
        tdlib_file = Path(tdjson_path)
        if tdlib_file.exists():
            print(f"[OK] TDLib найден: {tdjson_path}")
        else:
            print(f"[ОШИБКА] TDLib не найден: {tdjson_path}")
            return False
    
    print("\n[INFO] Создание клиента...")
    settings = ClientSettings(
        api_id=int(api_id),
        api_hash=api_hash,
        phone_number=phone_number,
        library_path=tdjson_path,
        proxy_settings=proxy_settings,
        device_model="POCO C65",
        system_version="Android 14",
        application_version="12.9.0",
    )
    
    client = Client(settings=settings)
    
    print("[INFO] Подключение к Telegram...")
    try:
        await client.start()
        print("[OK] Успешное подключение!")
        
        me = await client.api.get_me()
        print(f"[OK] Авторизован как: {me.first_name} {me.last_name or ''}")
        
        await client.stop()
        print("[OK] Клиент остановлен")
        return True
        
    except KeyboardInterrupt:
        print("\n[INFO] Прервано пользователем")
        await client.stop()
        return False
    except Exception as e:
        print(f"[ОШИБКА] Не удалось подключиться: {e}")
        print("\nВозможные причины:")
        print("1. Прокси не работает или заблокирован")
        print("2. Неправильный secret")
        print("3. Неправильный api_id/api_hash")
        print("\nПроверь PROXY_SETUP.md для решения проблем.")
        try:
            await client.stop()
        except:
            pass
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
