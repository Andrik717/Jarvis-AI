"""Локальные настройки Jarvis AI; секреты не хранятся в репозитории."""
from __future__ import annotations
import json, os
from pathlib import Path
from dataclasses import dataclass, asdict

APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "JarvisAI"
SETTINGS_FILE = APP_DIR / "settings.json"

@dataclass
class Settings:
    language: str = "ru"
    whisper_model: str = "small"
    compute_type: str = "int8"
    beam_size: int = 1
    vad_filter: bool = True
    tts_backend: str = "sapi"
    sapi_rate: int = 0
    sapi_volume: int = 100
    llm_base_url: str = ""
    llm_model: str = ""
    # API key intentionally loaded only from environment, never serialized.


def load_settings() -> Settings:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    allowed = Settings.__dataclass_fields__.keys()
    return Settings(**{k: v for k, v in data.items() if k in allowed})


def save_settings(settings: Settings) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_FILE)
