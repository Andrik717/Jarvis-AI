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
        fd, filename = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_dmitry_")
        os.close(fd)
        try:
            Path(filename).unlink(missing_ok=True)

            async def synthesize() -> None:
                communicate = edge_tts.Communicate(
                    text=text, voice=voice, rate="-2%", pitch="-2Hz", volume="+0%"
                )
                await communicate.save(filename)

            # Edge TTS иногда закрывает соединение без аудио. Повторяем
            # запрос, не меняя закреплённый мужской голос Дмитрия.
            last_error = None
            for attempt in range(3):
                try:
                    Path(filename).unlink(missing_ok=True)
                    asyncio.run(synthesize())
                    if not os.path.exists(filename) or os.path.getsize(filename) < 256:
                        raise RuntimeError("Edge TTS не создал аудио для ru-RU-DmitryNeural")
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    Path(filename).unlink(missing_ok=True)
                    if attempt < 2:
                        time.sleep(0.8 * (attempt + 1))
            if last_error is not None:
                raise RuntimeError(
                    "Не удалось получить аудио от Edge TTS после 3 попыток: "
                    + str(last_error)
                ) from last_error
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

    def reset_stop(self) -> None:
        """Сбрасывает флаг перед запуском новой задачи озвучки."""
        self._stop_event.clear()

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

    def speak_stream(self, chunks) -> None:
        """Озвучивает фразы по мере поступления текста от языковой модели."""
        buffer = ""
        for piece in chunks:
            if self._stop_event.is_set():
                return
            buffer += str(piece or "")
            while True:
                match = re.search(r"[.!?…;:]\s+|\n+", buffer)
                if match and match.end() >= 24:
                    phrase, buffer = buffer[:match.end()].strip(), buffer[match.end():]
                    if phrase:
                        self.speak(phrase)
                    continue
                if len(buffer) >= 190:
                    cut = buffer.rfind(" ", 80, 190)
                    if cut > 0:
                        phrase, buffer = buffer[:cut].strip(), buffer[cut:]
                        if phrase:
                            self.speak(phrase)
                        continue
                break
        if buffer.strip() and not self._stop_event.is_set():
            self.speak(buffer.strip())