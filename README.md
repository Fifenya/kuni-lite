# kuni-lite

Лёгкий Python-аналог [Kuni](https://github.com/Alex2772/kuni) под CPU-only ARM
(Oracle Cloud A1.Flex, 2 OCPU / 12GB RAM, без GPU).

Что есть:
- **Userbot через tdlib** (не Bot API) — видит чаты, читает, отвечает как обычный аккаунт.
- **Дневник с RAG** — SQLite + эмбеддинги, релевантные воспоминания подмешиваются в контекст перед каждым ответом.
- **Ночная консолидация памяти** — периодически сжимает/объединяет старые записи дневника (аналог "сна" у Kuni).
- **Working memory** — короткоживущий файл `data/working_memory.md`, всегда в контексте (незакрытые дела, обещания).
- **Переключаемый LLM-бэкенд** — `llm_backend = "ollama"` (локально, бесплатно, медленнее) или `"api"`
  (DeepSeek/OpenAI-совместимый эндпоинт, платно, быстрее и умнее) — переключается одной строкой в `config.toml`,
  без перезапуска не обязателен рестарт для part логики (сам конфиг читается заново при старте цикла).
- **TTS через Piper** — офлайн, чисто CPU, лёгкий (в отличие от OmniVoice, которому нужен GPU).

Чего нет (сознательно, чтобы не раздувать объём):
- прокси-сервер для IDE (`/v1/chat/completions` для Copilot и т.п.)
- Stable Diffusion / генерация картинок
- Prometheus/Grafana метрики
- отдельная обработка видео-сообщений

## Почему Python, а не C++

TDLib всё равно придётся **один раз собрать из исходников** на ARM — готовых бинарников `libtdjson.so`
под linux/arm64 в паблике больше нет (раньше были у `aiotdlib`, автор перестал их публиковать). Но это
разовая операция (`scripts/build_tdlib.sh`), а вся остальная логика (диалог, память, TTS, консолидация)
на Python пишется и правится на порядок быстрее, чем на C++/CMake, что критично, когда сервер слабый
и итерировать нужно быстро.

## Установка

```bash
# 1. системные зависимости для сборки tdlib
sudo apt update && sudo apt install -y build-essential cmake git zlib1g-dev \
  libssl-dev gperf php-cli python3-venv

# 2. собрать libtdjson.so (займёт время на 2 vCPU ARM — можно оставить на ночь)
bash scripts/build_tdlib.sh

# 3. python-окружение
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Piper (TTS), голос ru_RU
bash scripts/setup_piper.sh

# 5. конфиг
cp config.example.toml config.toml
# заполнить telegram_api_id/api_hash (my.telegram.org), owner_chat_id,
# llm_backend, ollama/api ключи

# 6. запуск
python main.py
```

Первый запуск попросит номер телефона/код — обычный вход в Telegram-аккаунт (используй отдельный
аккаунт для бота, не основной — userbot формально нарушает ToS Telegram).

## Структура

```
config.py            — загрузка + hot-reload config.toml
telegram_client.py    — обёртка над tdlib (aiotdlib), цикл обработки сообщений
llm/
  base.py             — общий интерфейс LLMBackend
  ollama_backend.py    — локальный Ollama (/api/chat)
  api_backend.py       — облачный OpenAI-совместимый API (DeepSeek и т.п.)
  router.py           — выбор бэкенда по config.llm_backend
memory/
  diary.py            — SQLite-хранилище дневника + эмбеддинги + поиск по косинусной близости
  working_memory.py    — data/working_memory.md, короткая память на 1-3 дня
  consolidate.py       — ночная консолидация/сжатие дневника
tts/
  piper_tts.py         — синтез голосовых через Piper
main.py                — точка входа, склеивает всё вместе
```
