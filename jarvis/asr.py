"""Облачное распознавание OpenAI с локальным Whisper как резервом."""
from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request
import wave

import numpy as np

from .config import Settings


class SpeechRecognizer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    def _wav_bytes(self, audio: np.ndarray) -> bytes:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        samples = np.clip(samples, -1.0, 1.0)
        pcm = (samples * 32767.0).astype("<i2").tobytes()
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(pcm)
        return output.getvalue()

    def _transcribe_cloud(self, audio: np.ndarray, api_key: str) -> str:
        audio_data = self._wav_bytes(audio)
        if len(audio_data) > 24 * 1024 * 1024:
            raise RuntimeError(
                "Голосовое сообщение слишком большое для отправки. "
                "Запишите его короче или используйте локальное распознавание."
            )

        boundary = "----JarvisAudioBoundary7MA4YWxkTrZu0gW"
        parts = []

        def field(name: str, value: str) -> None:
            parts.append((
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8"))

        field("model", "gpt-transcribe")
        field("languages[]", "ru")
        field(
            "prompt",
            "Разговорная речь на русском языке. Сохраняй исходный смысл, "
            "падежи, окончания, имена собственные и названия программ. "
            "Не заменяй непонятные слова догадками и не добавляй слова, "
            "которых не было в аудио. Контекст: пользователь разговаривает "
            "с голосовым помощником Джарвисом о Windows, настройках и "
            "компьютере."
        )
        for keyword in (
            "Джарвис", "Jarvis", "Windows", "Ollama", "Whisper",
            "Telegram", "Steam", "YouTube", "Екатеринбург", "Москва",
            "PowerShell", "Python", "микрофон", "распознавание речи",
        ):
            field("keywords[]", keyword)
        parts.append(
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="jarvis_voice.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n".encode("utf-8")
            + audio_data + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode("ascii"))
        body = b"".join(parts)

        request = urllib.request.Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:700]
            raise RuntimeError(
                f"Облачное распознавание OpenAI вернуло HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Не удалось связаться с сервисом распознавания OpenAI. "
                f"Проверьте интернет. Подробности: {getattr(exc, 'reason', exc)}"
            ) from exc

        text = str(result.get("text") or "").strip()
        if not text:
            raise RuntimeError("Сервис распознавания вернул пустой текст.")
        return text

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

    def _transcribe_local(self, audio: np.ndarray) -> str:
        segments, _ = self._get_model().transcribe(
            audio.astype(np.float32, copy=False),
            language=self.settings.language,
            beam_size=max(1, min(5, int(self.settings.beam_size))),
            vad_filter=self.settings.vad_filter,
            condition_on_previous_text=False,
            initial_prompt=(
                "Это естественный разговор пользователя с голосовым помощником "
                "Джарвисом на русском языке. Сохраняй разговорную форму, окончания, "
                "отрицания, числа и вопросительную интонацию. Не додумывай слова. "
                "Если слово неразборчиво, не подменяй его похожим по теме. "
                "Возможные названия и термины: Джарвис, Jarvis, Ollama, Windows, "
                "Telegram, Steam, YouTube, Екатеринбург, Москва, Whisper, "
                "PowerShell, Python, микрофон, распознавание речи."
            ),
            temperature=0.0,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if api_key:
            return self._transcribe_cloud(audio, api_key)
        return self._transcribe_local(audio)
