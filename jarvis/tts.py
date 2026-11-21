"""Озвучка. SAPI — базовый Windows backend; ошибки не маскируются."""
from __future__ import annotations
import platform
from .config import Settings

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
            # Предпочитаем русскую установленную системную голосовую модель.
            voices = self._engine.GetVoices()
            for i in range(voices.Count):
                voice = voices.Item(i)
                desc = str(voice.GetDescription()).lower()
                if "russian" in desc or "рус" in desc:
                    self._engine.Voice = voice
                    break
        return self._engine

    def speak(self, text: str) -> None:
        text = " ".join(str(text).split())
        if not text:
            return
        if self.settings.tts_backend == "sapi":
            self._sapi().Speak(text, 1)  # асинхронно, UI не блокируется
        else:
            raise RuntimeError(f"Неизвестный TTS backend: {self.settings.tts_backend}")
