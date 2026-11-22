"""Безопасные голосовые команды для Windows: приложения, сайты, поиск и папки."""
from __future__ import annotations

import json
from difflib import SequenceMatcher
import os
import re
import subprocess
from html.parser import HTMLParser
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus


class _DuckDuckGoParser(HTMLParser):
    """Извлекает заголовки, ссылки и краткие описания из HTML-поиска."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self._capture = None
        self._current = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._current = {"title": "", "url": attributes.get("href", ""), "snippet": ""}
            self.results.append(self._current)
            self._capture = "title"
        elif "result__snippet" in classes and self.results:
            self._current = self.results[-1]
            self._capture = "snippet"

    def handle_data(self, data):
        if self._current is not None and self._capture in ("title", "snippet"):
            self._current[self._capture] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._capture == "title":
            self._capture = None
        elif tag in ("div", "span") and self._capture == "snippet":
            self._capture = None


def _search_web(query: str) -> str:
    """Возвращает реальные результаты поиска в чат, не исполняя команды."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; JarvisAI/1.0)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            page = response.read().decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return f"Не удалось получить результаты поиска: {str(exc)[:140]}."

    parser = _DuckDuckGoParser()
    parser.feed(page)
    results = []
    for item in parser.results:
        title = re.sub(r"\s+", " ", item["title"]).strip()
        snippet = re.sub(r"\s+", " ", item["snippet"]).strip()
        result_url = item["url"].strip()
        parsed = urllib.parse.urlparse(result_url)
        if "duckduckgo.com" in parsed.netloc:
            result_url = urllib.parse.parse_qs(parsed.query).get("uddg", [result_url])[0]
        if result_url.startswith("//"):
            result_url = "https:" + result_url
        if title and result_url.startswith(("http://", "https://")):
            results.append((title, snippet, result_url))
        if len(results) >= 4:
            break

    if not results:
        return "Поисковая система не вернула читаемых результатов. Попробуй сформулировать запрос иначе."

    lines = [f"Результаты поиска по запросу «{query}»: "]
    for index, (title, snippet, result_url) in enumerate(results, 1):
        lines.append(f"{index}. {title}")
        if snippet:
            lines.append(snippet)
        lines.append(result_url)
    return "\n".join(lines)


def _normalize(value: str) -> str:
    text = str(value or "").casefold().replace("ё", "е")
    text = re.sub(r"[^а-яa-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^(?:эй )?джарвис[ ,]*", "", text).strip()


def _is_close_alias(target: str, aliases: tuple[str, ...]) -> bool:
    """Осторожно распознаёт очевидную одиночную опечатку в известной команде."""
    if len(target) < 5 or len(target.split()) > 2:
        return False
    return any(SequenceMatcher(None, target, alias).ratio() >= 0.82 for alias in aliases)


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
        # Учитываем частые формы русских городов и типичную ошибку Whisper
        # «Москверо» вместо «Москва». Не используем первый результат геокодера вслепую.
        aliases = {
            "москверо": "Москва",
            "москве": "Москва",
            "екатеринбурге": "Екатеринбург",
            "питере": "Санкт-Петербург",
            "петербурге": "Санкт-Петербург",
            "нижнем новгороде": "Нижний Новгород",
            "новосибирске": "Новосибирск",
            "казани": "Казань",
        }
        requested_city = aliases.get(city.casefold(), city)
        candidates = [requested_city]
        for ending in ("е", "и", "у", "ю", "ом", "ем"):
            if requested_city.casefold().endswith(ending) and len(requested_city) > len(ending) + 2:
                candidates.append(requested_city[:-len(ending)])
                break

        places = []
        requested_key = _normalize(requested_city)
        for candidate in dict.fromkeys(candidates):
            geo_url = (
                "https://geocoding-api.open-meteo.com/v1/search?"
                + urllib.parse.urlencode({"name": candidate, "count": 5, "language": "ru", "format": "json"})
            )
            request = urllib.request.Request(geo_url, headers={"User-Agent": "JarvisAI/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                results = json.loads(response.read().decode("utf-8")).get("results") or []
            places = [
                item for item in results
                if _normalize(str(item.get("name", ""))) == requested_key
            ]
            if places:
                break
        if not places:
            return (
                f"Не могу надёжно определить город «{city}». "
                "Уточни название, чтобы я не показал погоду для другого места."
            )

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

    # Любой вопрос о погоде перехватываем до локальной модели.
    # Это не позволяет модели выдавать выдуманные шаблоны вместо прогноза.
    if re.search(r"\b(?:погод\w*|температур\w*)\b", text):
        city_match = re.search(r"\b(?:в|для)\s+(.+)$", text)
        if not city_match:
            return "Конечно. В каком городе проверить погоду?"
        city = city_match.group(1).strip()
        if city in ("сейчас", "сегодня", "завтра"):
            return "Назови город, для которого проверить погоду."
        return _weather_for_city(city)

    # Поиск в интернете: возвращаем заголовки и краткие описания в чат.
    search_match = re.match(
        r"^(?:найди(?: в интернете)?|поищи(?: в интернете)?|загугли)\s+(.+)$",
        text,
    )
    if search_match:
        query = search_match.group(1).strip()
        if query:
            return _search_web(query)

    if text in ("новости", "последние новости", "что нового"):
        return _search_web("последние новости сегодня")

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
    site_match = re.match(r"^(?:открой(?:те)?|открою|открывай(?:те)?|запусти(?:те)?|запускай(?:те)?|включи(?:те)?|включай(?:те)?|перейди на|перейдите на)\s+(?:сайт\s+)?(.+)$", text)
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
        "диспетчер задач": (("диспетчер задач", "диспетчер"), ["taskmgr.exe"]),
        "paint": (("paint", "пейнт", "рисование"), ["mspaint.exe"]),
        "ножницы": (("ножницы", "снимок экрана"), ["SnippingTool.exe"]),
    }
    app_match = re.match(r"^(?:открой(?:те)?|открою|открывай(?:те)?|запусти(?:те)?|запускай(?:те)?|включи(?:те)?|включай(?:те)?|покажи)\s+(.+)$", text)
    if app_match:
        target = app_match.group(1).strip()
        for display, (aliases, command) in apps.items():
            if target in aliases or _is_close_alias(target, aliases):
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

        if target in ("параметры", "настройки windows", "настройки системы"):
            try:
                if os.name != "nt":
                    return "Открытие параметров Windows доступно только в Windows."
                os.startfile("ms-settings:")
                return "Открываю параметры Windows."
            except OSError as exc:
                return f"Не удалось открыть параметры Windows. Причина: {exc}"

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
