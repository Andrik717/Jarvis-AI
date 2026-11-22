"""Проверка Edge TTS отдельно от интерфейса Jarvis."""
from __future__ import annotations

import asyncio
import importlib.metadata
import os
import platform
import sys
import tempfile
from pathlib import Path

VOICE = "ru-RU-DmitryNeural"
TEXT = "Здравствуйте. Это проверка мужского голоса Дмитрия."


async def main() -> int:
    try:
        version = importlib.metadata.version("edge-tts")
    except importlib.metadata.PackageNotFoundError:
        print("ОШИБКА: пакет edge-tts не установлен.")
        return 2

    print("JARVIS EDGE TTS DIAGNOSTICS")
    print(f"Python: {sys.version.split()[0]}")
    print(f"OS: {platform.platform()}")
    print(f"edge-tts: {version}")
    print(f"Голос: {VOICE}")

    try:
        import edge_tts
        fd, name = tempfile.mkstemp(prefix="jarvis_edge_test_", suffix=".mp3")
        os.close(fd)
        path = Path(name)
        try:
            communicate = edge_tts.Communicate(
                text=TEXT, voice=VOICE, rate="-2%", pitch="-2Hz", volume="+0%"
            )
            await communicate.save(str(path))
            size = path.stat().st_size if path.exists() else 0
            if size < 128:
                print(f"ОШИБКА: Edge TTS не создал полноценный MP3 (размер: {size} байт).")
                return 3
            print(f"УСПЕХ: Edge TTS создал MP3 ({size} байт).")
            print("Если звук не слышен в приложении, проблема уже после синтеза: проигрыватель/аудиоустройство.")
            return 0
        finally:
            path.unlink(missing_ok=True)
    except Exception as exc:
        print("ОШИБКА EDGE TTS:")
        print(f"{type(exc).__name__}: {exc}")
        print("Это отдельный тест без интерфейса Jarvis; причина находится в библиотеке, сети, TLS/прокси или сервисе Edge TTS.")
        return 4


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
