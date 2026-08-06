#!/bin/bash
# Собирает libtdjson.so из исходников — на linux/arm64 готовых бинарников
# для aiotdlib больше не публикуют, так что делаем это один раз сами.
# На 2 vCPU ARM (Oracle A1.Flex) сборка может занять 40-90 минут.
set -euo pipefail

TDLIB_COMMIT="master"   # можно закрепить конкретный коммит для стабильности
TARGET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/tdlib"

sudo apt-get update
sudo apt-get install -y build-essential cmake git zlib1g-dev libssl-dev gperf php-cli

mkdir -p "$TARGET_DIR"
cd /tmp
rm -rf td
git clone https://github.com/tdlib/td.git
cd td
git checkout "$TDLIB_COMMIT"

mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DTD_ENABLE_LTO=OFF ..
# -j2: ограничиваем параллелизм, чтобы не съесть всю RAM на слабом инстансе
cmake --build . -j2 --target tdjson

cp libtdjson.so* "$TARGET_DIR/"

echo "libtdjson.so собран и лежит в $TARGET_DIR"
echo "Укажи путь в config.toml -> [telegram] tdjson_path"
