"""Естественная нейросетевая озвучка Edge TTS с резервным Windows SAPI."""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
import time
from pathlib import Path
import platform

from .config import Settings


def _speech_text(value: str) -> str:
    """Убирает разметку, которую не нужно читать вслух."""
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

        voice = getattr(self.settings, "tts_voice", "ru-RU-SvetlanaNeural")

        async def synthesize(path):
            communicate = edge_tts.Communicate(
                text, voice, rate="-2%", pitch="-2Hz", volume="+0%"
            )
            await communicate.save(path)

        fd, filename = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_voice_")
        os.close(fd)
        try:
            asyncio.run(synthesize(filename))
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.08)
            pygame.mixer.music.unload()
        finally:
            try:
                Path(filename).unlink(missing_ok=True)
            except OSError:
                pass

    def speak(self, text: str) -> None:
        text = _speech_text(text)
        if not text:
            return
        if self.settings.tts_backend == "edge":
            self._edge(text)
        elif self.settings.tts_backend == "sapi":
            self._sapi().Speak(text, 0)
        else:
            raise RuntimeError(f"Неизвестный TTS backend: {self.settings.tts_backend}")
