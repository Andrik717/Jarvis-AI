"""Захват аудио с микрофона через sounddevice."""
from __future__ import annotations
import sounddevice as sd
import numpy as np

class Microphone:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def record(self, seconds: float = 5.0) -> np.ndarray:
        frames = int(self.sample_rate * max(0.5, min(20.0, seconds)))
        audio = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return audio.reshape(-1)
