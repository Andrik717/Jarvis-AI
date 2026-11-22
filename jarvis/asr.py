"""Полностью локальное распознавание русской речи через faster-whisper."""
from __future__ import annotations

import numpy as np

from .config import Settings


class SpeechRecognizer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.settings.whisper_model,
                device="cpu",
                compute_type=self.settings.compute_type,
                cpu_threads=0,
                num_workers=1,
            )
        return self._model

    def _transcribe_local(self, audio: np.ndarray, context: str = "") -> str:
        prompt = (
            "Это естественный разговор пользователя с голосовым помощником Джарвисом на русском языке. "
            "Сохраняй разговорную форму, окончания, отрицания, числа и вопросительную интонацию. "
            "Не додумывай слова и не подменяй неразборчивое слово догадкой. "
            "Возможные названия: Джарвис, Jarvis, Ollama, Windows, Telegram, Steam, YouTube, "
            "Екатеринбург, Москва, Whisper, PowerShell, Python, микрофон. "
            + ("Недавний контекст разговора: " + context[:350] if context else "")
        )
        segments, _ = self._get_model().transcribe(
            audio.astype(np.float32, copy=False),
            language=self.settings.language,
            beam_size=max(1, min(5, int(self.settings.beam_size))),
            vad_filter=self.settings.vad_filter,
            condition_on_previous_text=False,
            initial_prompt=prompt,
            temperature=0.0,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def transcribe(self, audio: np.ndarray, context: str = "") -> str:
        if audio.size == 0:
            return ""
        # Распознавание всегда локальное: никаких платных API и отправки аудио в облако.
        return self._transcribe_local(audio, context)
