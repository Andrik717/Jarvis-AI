"""Точка входа Jarvis AI."""
from .config import load_settings

def main() -> None:
    settings = load_settings()
    print("JARVIS AI • начальная сборка")
    print(f"Язык распознавания: {settings.language}")
    print(f"Модель Whisper: {settings.whisper_model} | beam={settings.beam_size}")
    print("Настройки сохранены локально. Голосовой интерфейс подключается следующим этапом.")

if __name__ == "__main__":
    main()
