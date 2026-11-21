"""Надёжная пофразовая озвучка Edge TTS с повторами и резервной генерацией."""
from __future__ import annotations

import asyncio
import os
import queue
import re
import tempfile
import threading
import time
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


def _speech_chunks(text: str, limit: int = 260, first_limit: int = 110) -> list[str]:
    """Делит ответ так, чтобы первую короткую часть можно было озвучить быстрее."""
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        chunk_limit = first_limit if not chunks and not current else limit
        while len(sentence) > chunk_limit:
            cut = sentence.rfind(" ", 0, chunk_limit + 1)
            if cut < 1:
                cut = chunk_limit
            part, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            if current:
                chunks.append(current)
                current = ""
            if part:
                chunks.append(part)
            chunk_limit = limit
        if sentence:
            candidate = f"{current} {sentence}".strip()
            chunk_limit = first_limit if not chunks else limit
            if current and len(candidate) > chunk_limit:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


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

        voice = self.settings.tts_voice or "ru-RU-DmitryNeural"
        chunks = _speech_chunks(text)
        audio_queue: queue.Queue = queue.Queue()
        temporary_files: list[str] = []

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        async def save_audio(phrase: str, filename: str) -> None:
            last_error = None
            # Edge TTS иногда закрывает соединение без аудио. Повторяем запрос,
            # прежде чем переходить к резервному варианту.
            for attempt in range(3):
                try:
                    Path(filename).unlink(missing_ok=True)
                    communicate = edge_tts.Communicate(
                        phrase, voice, rate="-2%", pitch="-2Hz", volume="+0%"
                    )
                    await communicate.save(filename)
                    if not os.path.exists(filename) or os.path.getsize(filename) < 256:
                        raise RuntimeError("Edge TTS вернул пустой аудиофайл")
                    return
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        await asyncio.sleep(0.6 * (attempt + 1))
            raise RuntimeError(f"Edge TTS не создал аудио после 3 попыток: {last_error}")

        async def prepare_audio():
            try:
                index = 0
                while index < len(chunks):
                    fd, filename = tempfile.mkstemp(
                        suffix=".mp3", prefix="jarvis_voice_"
                    )
                    os.close(fd)
                    temporary_files.append(filename)
                    try:
                        await save_audio(chunks[index], filename)
                        audio_queue.put(("file", filename))
                        index += 1
                        # Небольшая пауза снижает риск ограничения частоты запросов.
                        await asyncio.sleep(0.2)
                    except Exception:
                        Path(filename).unlink(missing_ok=True)
                        fallback = " ".join(chunks[index:]).strip()
                        fd, fallback_file = tempfile.mkstemp(
                            suffix=".mp3", prefix="jarvis_voice_fallback_"
                        )
                        os.close(fd)
                        temporary_files.append(fallback_file)
                        await save_audio(fallback, fallback_file)
                        audio_queue.put(("file", fallback_file))
                        break
            except Exception as exc:
                audio_queue.put(("error", exc))
            finally:
                audio_queue.put(("done", None))

        def producer():
            asyncio.run(prepare_audio())

        worker = threading.Thread(target=producer, daemon=True)
        worker.start()
        try:
            while True:
                kind, value = audio_queue.get()
                if kind == "done":
                    break
                if kind == "error":
                    raise value
                pygame.mixer.music.load(value)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.04)
                pygame.mixer.music.unload()
        finally:
            worker.join()
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
            for filename in temporary_files:
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
