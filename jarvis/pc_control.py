"""Безопасные локальные команды управления Windows."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def handle_command(user_text: str) -> str | None:
    """Выполняет только заранее разрешённые команды запуска приложений."""
    text = re.sub(r"[^а-яёa-z0-9 ]+", " ", str(user_text).casefold())
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(джарвис|эй джарвис)[ ,]*", "", text).strip()

    commands = {
        "браузер": ("браузер", "открой браузер", "запусти браузер", "открыть браузер"),
        "блокнот": ("блокнот", "открой блокнот", "запусти блокнот", "открыть блокнот"),
        "калькулятор": ("калькулятор", "открой калькулятор", "запусти калькулятор", "открыть калькулятор"),
        "проводник": ("проводник", "открой проводник", "открой папки", "запусти проводник", "открыть проводник"),
    }
    selected = next(
        (app for app, phrases in commands.items() if text in phrases),
        None,
    )
    if selected is None:
        return None

    try:
        if selected == "браузер":
            os.startfile("https://www.google.com")
        elif selected == "блокнот":
            subprocess.Popen(["notepad.exe"])
        elif selected == "калькулятор":
            subprocess.Popen(["calc.exe"])
        elif selected == "проводник":
            subprocess.Popen(["explorer.exe", str(Path.home())])
    except OSError as exc:
        return f"Не удалось открыть {selected}. Причина: {exc}"

    names = {
        "браузер": "браузер",
        "блокнот": "блокнот",
        "калькулятор": "калькулятор",
        "проводник": "проводник",
    }
    return f"Открываю {names[selected]}."
