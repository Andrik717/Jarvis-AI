"""Непрерывный захват голосового сообщения с микрофона через sounddevice."""
from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd


class Microphone:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._stream = None
        self._chunks = []
        self._lock = threading.Lock()

    def _audio_callback(self, indata, frames, time_info, status):
        # Callback вызывается аудиопотоком; копируем данные до следующего вызова.
        if status:
            pass
        with self._lock:
            self._chunks.append(indata[:, 0].copy())

    def start_recording(self):
        """Начинает запись без блокировки интерфейса."""
        if self._stream is not None:
            raise RuntimeError("Запись уже выполняется")
        with self._lock:
            self._chunks = []
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        try:
            stream.start()
        except Exception:
            stream.close()
            raise
        self._stream = stream

    def stop_recording(self) -> np.ndarray:
        """Останавливает запись и возвращает весь накопленный звук."""
        stream = self._stream
        if stream is None:
            return np.array([], dtype=np.float32)
        self._stream = None
        try:
            stream.stop()
        finally:
            stream.close()
        with self._lock:
            chunks = self._chunks
            self._chunks = []
        if not chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32, copy=False)

    def record(self, seconds: float = 5.0) -> np.ndarray:
        """Совместимость со старым способом записи для возможных внешних вызовов."""
        frames = int(self.sample_rate * max(0.5, min(20.0, seconds)))
        audio = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return audio.reshape(-1)
