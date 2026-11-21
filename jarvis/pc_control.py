"""Безопасные голосовые команды для Windows: приложения, сайты, поиск и папки."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
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


def _weather_for_city(city: str) -> str:
    """Получает текущую погоду через Open-Meteo; API-ключ не требуется."""
    city = city.strip()
    if not city:
        return "Назови город, и я проверю погоду."
    try:
        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode({"name": city, "count": 1, "language": "ru", "format": "json"})
        )
        request = urllib.request.Request(geo_url, headers={"User-Agent": "JarvisAI/1.0"})
        with urllib.request.urlopen(request, timeout=8) as response:
            places = json.loads(response.read().decode("utf-8")).get("results") or []
        if not places:
            return f"Не нашёл город «{city}». Проверь название и попробуй ещё раз."

        place = places[0]
        params = {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "timezone": "auto",
        }
        forecast_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(forecast_url, headers={"User-Agent": "JarvisAI/1.0"})
        with urllib.request.urlopen(request, timeout=8) as response:
            current = json.loads(response.read().decode("utf-8")).get("current") or {}

        code = current.get("weather_code")
        descriptions = {
            0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность",
            3: "пасмурно", 45: "туман", 48: "изморозевый туман",
            51: "небольшая морось", 53: "морось", 55: "сильная морось",
            56: "ледяная морось", 57: "сильная ледяная морось",
            61: "небольшой дождь", 63: "дождь", 65: "сильный дождь",
            66: "ледяной дождь", 67: "сильный ледяной дождь",
            71: "небольшой снег", 73: "снег", 75: "сильный снег",
            77: "снежные зёрна", 80: "небольшой ливень", 81: "ливень",
            82: "сильный ливень", 85: "снегопад", 86: "сильный снегопад",
            95: "гроза", 96: "гроза с небольшим градом", 99: "гроза с сильным градом",
        }
        condition = descriptions.get(code, "условия не определены")
        city_name = place.get("name", city)
        region = place.get("admin1")
        location = f"{city_name}, {region}" if region and region != city_name else city_name
        parts = [f"Сейчас в {location}: {condition}."]
        if current.get("temperature_2m") is not None:
            parts.append(f"Температура {current['temperature_2m']:.0f} °C.")
        if current.get("apparent_temperature") is not None:
            parts.append(f"Ощущается как {current['apparent_temperature']:.0f} °C.")
        if current.get("relative_humidity_2m") is not None:
            parts.append(f"Влажность {current['relative_humidity_2m']}%.")
        if current.get("wind_speed_10m") is not None:
            parts.append(f"Ветер {current['wind_speed_10m']} км/ч.")
        if current.get("precipitation") is not None and current["precipitation"] > 0:
            parts.append(f"Осадки: {current['precipitation']} мм.")
        if current.get("time"):
            parts.append(f"Данные на {current['time'].replace('T', ' ')} по местному времени.")
        return " ".join(parts)
    except (OSError, urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        return f"Не удалось получить актуальную погоду для {city}: {str(exc)[:100]}. Проверь подключение к интернету."


def handle_command(user_text: str) -> str | None:
    """Выполняет только заранее разрешённые команды, иначе отдаёт фразу ИИ."""
    text = _normalize(user_text)
    if not text:
        return None

    # Погода: отвечаем только по данным реального погодного сервиса, не по догадкам модели.
    weather_match = re.match(
        r"^(?:какая погода|погода|что с погодой|температура)\s+(?:сейчас\s+)?(?:в|для)\s+(.+)$",
        text,
    )
    if weather_match:
        return _weather_for_city(weather_match.group(1).strip())

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
