"""Локальное распознавание речи. Модель загружается лениво и переиспользуется."""
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

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        segments, _ = self._get_model().transcribe(
            audio.astype(np.float32, copy=False),
            language=self.settings.language,
            beam_size=max(1, min(5, int(self.settings.beam_size))),
            vad_filter=self.settings.vad_filter,
            condition_on_previous_text=False,
            temperature=0.0,
        )
        return " ".join(s.text.strip() for s in segments).strip()
