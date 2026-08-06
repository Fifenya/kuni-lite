#!/bin/bash
# Скачивает русский голос для Piper (полностью CPU, ARM-совместимо через onnxruntime).
set -euo pipefail

TARGET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/tts/voices"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium"
curl -L -o ru_RU-irina-medium.onnx "$BASE_URL/ru_RU-irina-medium.onnx"
curl -L -o ru_RU-irina-medium.onnx.json "$BASE_URL/ru_RU-irina-medium.onnx.json"

echo "Голос сохранён в $TARGET_DIR"
echo "Проверь актуальную ссылку на huggingface.co/rhasspy/piper-voices, если ссылка выше уже неактуальна."
