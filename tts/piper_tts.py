from __future__ import annotations

import io
import wave
from pathlib import Path


class PiperTTS:
    """Офлайн TTS на CPU через Piper (onnxruntime, есть сборки под arm64 —
    в отличие от OmniVoice из оригинального Kuni, GPU тут не нужен вообще)."""

    def __init__(self, voice_model_path: str):
        self.voice_model_path = Path(voice_model_path)
        self._voice = None

    def _ensure_loaded(self):
        if self._voice is not None:
            return
        try:
            from piper import PiperVoice
        except ImportError as e:
            raise RuntimeError(
                "Пакет piper-tts не установлен. pip install piper-tts, "
                "и скачай голос через scripts/setup_piper.sh"
            ) from e

        if not self.voice_model_path.exists():
            raise RuntimeError(
                f"Голосовая модель не найдена: {self.voice_model_path}. "
                "Запусти scripts/setup_piper.sh"
            )

        self._voice = PiperVoice.load(str(self.voice_model_path))

    def synthesize_to_wav_bytes(self, text: str) -> bytes:
        """Возвращает готовый .wav как bytes — можно сразу слать в Telegram
        как voice message (предварительно сконвертировав в .ogg/opus, см. main.py)."""
        self._ensure_loaded()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._voice.synthesize(text, wav_file)
        return buf.getvalue()
