"""Надёжная цельная озвучка Edge TTS закреплённым мужским голосом Дмитрия."""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
import time
import threading
from pathlib import Path
import platform

from .config import Settings


def _speech_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"```.*?```", " Фрагмент кода опущен. ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "ссылка", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"\n{2,}", ". ", text)
    return " ".join(text.split()).strip()


class SpeechOutput:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine = None
        self._stop_event = threading.Event()

    def _sapi(self):
        if platform.system() != "Windows":
            raise RuntimeError("SAPI backend доступен только в Windows")
        if self._engine is None:
            import win32com.client
            self._engine = win32com.client.Dispatch("SAPI.SpVoice")
            self._engine.Rate = max(-10, min(10, int(self.settings.sapi_rate)))
            self._engine.Volume = max(0, min(100, int(self.settings.sapi_volume)))
            voices = self._engine.GetVoices()
            for i in range(voices.Count):
                voice = voices.Item(i)
                desc = str(voice.GetDescription()).lower()
                if "russian" in desc or "рус" in desc:
                    self._engine.Voice = voice
                    break
        return self._engine

    def _edge(self, text: str) -> None:
        import edge_tts
        import pygame

        voice = "ru-RU-DmitryNeural"
        self._stop_event.clear()
        fd, filename = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_dmitry_")
        os.close(fd)
        try:
            Path(filename).unlink(missing_ok=True)

            async def synthesize() -> None:
                communicate = edge_tts.Communicate(
                    text=text, voice=voice, rate="-2%", pitch="-2Hz", volume="+0%"
                )
                await communicate.save(filename)

            # Возвращаем цельную генерацию: именно этот вариант раньше
            # давал пользователю подтверждённый мужской голос.
            asyncio.run(synthesize())
            if not os.path.exists(filename) or os.path.getsize(filename) < 256:
                raise RuntimeError("Edge TTS не создал аудио для ru-RU-DmitryNeural")
            if self._stop_event.is_set():
                return

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                time.sleep(0.04)
            pygame.mixer.music.unload()
        finally:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
            Path(filename).unlink(missing_ok=True)

    def stop(self) -> None:
        """Останавливает текущую озвучку; безопасен и до начала воспроизведения."""
        self._stop_event.set()
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def speak(self, text: str) -> None:
        text = _speech_text(text)
        if text:
            self._edge(text)
