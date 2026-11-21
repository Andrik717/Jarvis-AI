"""Безопасные голосовые команды для Windows: приложения, сайты, поиск и папки."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus


def _normalize(value: str) -> str:
    text = str(value or "").casefold().replace("ё", "е")
    text = re.sub(r"[^а-яa-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^(?:эй )?джарвис[ ,]*", "", text).strip()


def _open_url(url: str) -> None:
    if not webbrowser.open(url, new=2):
        raise OSError("Windows не смогла открыть браузер по умолчанию")


def _open_folder(folder: str) -> None:
    home = Path.home()
    candidates = {
        "загрузки": (home / "Downloads", home / "Загрузки"),
        "рабочий стол": (home / "Desktop", home / "Рабочий стол"),
        "документы": (home / "Documents", home / "Документы"),
    }
    path = next((item for item in candidates[folder] if item.exists()), home)
    subprocess.Popen(["explorer.exe", str(path)])


def handle_command(user_text: str) -> str | None:
    """Выполняет только заранее разрешённые команды, иначе отдаёт фразу ИИ."""
    text = _normalize(user_text)
    if not text:
        return None

    # Поиск в интернете: открываем запрос в браузере, ничего не исполняем.
    search_match = re.match(
        r"^(?:найди(?: в интернете)?|поищи(?: в интернете)?|загугли)\s+(.+)$",
        text,
    )
    if search_match:
        query = search_match.group(1).strip()
        if query:
            try:
                _open_url("https://www.google.com/search?q=" + quote_plus(query))
                return f"Ищу в интернете: {query}."
            except OSError as exc:
                return f"Не удалось открыть поиск. Причина: {exc}"

    # Разрешённые сайты и их разговорные названия.
    websites = {
        "ютуб": ("youtube", "https://www.youtube.com"),
        "youtube": ("YouTube", "https://www.youtube.com"),
        "гугл": ("Google", "https://www.google.com"),
        "google": ("Google", "https://www.google.com"),
        "яндекс": ("Яндекс", "https://ya.ru"),
        "вк": ("ВКонтакте", "https://vk.com"),
        "вконтакте": ("ВКонтакте", "https://vk.com"),
        "стим": ("Steam", "https://store.steampowered.com"),
        "steam": ("Steam", "https://store.steampowered.com"),
        "телеграм": ("Telegram", "https://web.telegram.org"),
        "telegram": ("Telegram", "https://web.telegram.org"),
        "чат гпт": ("ChatGPT", "https://chatgpt.com"),
        "chatgpt": ("ChatGPT", "https://chatgpt.com"),
        "почту": ("почту", "https://mail.google.com"),
        "почта": ("почту", "https://mail.google.com"),
    }
    site_match = re.match(r"^(?:открой|запусти|перейди на)\s+(?:сайт\s+)?(.+)$", text)
    if site_match:
        target = site_match.group(1).strip()
        if target in websites:
            name, url = websites[target]
            try:
                _open_url(url)
                return f"Открываю {name}."
            except OSError as exc:
                return f"Не удалось открыть {name}. Причина: {exc}"

    # Программы Windows.
    apps = {
        "блокнот": (("блокнот", "notepad"), ["notepad.exe"]),
        "калькулятор": (("калькулятор", "кальк"), ["calc.exe"]),
        "проводник": (("проводник", "папки"), ["explorer.exe", str(Path.home())]),
    }
    app_match = re.match(r"^(?:открой|запусти|включи)\s+(.+)$", text)
    if app_match:
        target = app_match.group(1).strip()
        for display, (aliases, command) in apps.items():
            if target in aliases:
                try:
                    subprocess.Popen(command)
                    return f"Открываю {display}."
                except OSError as exc:
                    return f"Не удалось открыть {display}. Причина: {exc}"

        if target in ("браузер", "интернет"):
            try:
                _open_url("https://www.google.com")
                return "Открываю браузер."
            except OSError as exc:
                return f"Не удалось открыть браузер. Причина: {exc}"

        folder_aliases = {
            "загрузки": "загрузки", "папку загрузки": "загрузки",
            "рабочий стол": "рабочий стол",
            "документы": "документы", "папку документы": "документы",
        }
        if target in folder_aliases:
            try:
                _open_folder(folder_aliases[target])
                return f"Открываю папку «{folder_aliases[target]}»."
            except OSError as exc:
                return f"Не удалось открыть папку. Причина: {exc}"

    return None
