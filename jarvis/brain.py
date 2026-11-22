"""Локальный ИИ-мозг Джарвиса: память, контекст и связный диалог."""
from __future__ import annotations
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from .config import APP_DIR

HISTORY_FILE = APP_DIR / "conversation.json"
MEMORY_FILE = APP_DIR / "memory.json"
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 9000
MAX_MEMORIES = 50
MAX_MEMORY_CHARS = 2200

SYSTEM_PROMPT = (
    "Твоё имя — Джарвис. Ты персональный цифровой помощник пользователя: умный, "
    "спокойный, внимательный, самостоятельный и надёжный. Общайся естественно, "
    "как компетентный собеседник, а не как робот или справочник. Русский язык — основной. "
    "Не обращайся к пользователю по имени, пока он сам не попросит и имя не подтверждено. "
    "Не копируй реплики персонажей из фильмов. "
    "\n\nПРИНЦИПЫ МЫШЛЕНИЯ И ДОСТОВЕРНОСТИ: "
    "1) Сначала пойми, что именно хочет пользователь, затем отвечай по существу. Если входная фраза пришла из распознавания речи, учитывай вероятность фонетических ошибок, пропущенных окончаний и опечаток. Исправляй только очевидные ошибки, когда контекст однозначно подтверждает исходное слово; не переписывай смысл и не выполняй опасное действие на основе догадки — в таком случае переспроси. "
    "Учитывай всю переданную историю диалога, недавние решения, исправления и ограничения. Не говори, что не видишь предыдущие сообщения, если они присутствуют в истории. "
    "Если пользователь цитирует ответ Джарвиса или присылает фрагмент переписки, определи, чьи это слова и на какой вопрос они отвечали; не принимай цитату за новую ошибку или команду. Короткие реплики «да», «давай», «продолжай», «а дальше?», «сделай это» относятся "
    "к текущей теме, если контекст не указывает на другое. Не заставляй повторять известное. "
    "2) Не выдумывай факты, цифры, источники, события, результаты поиска, погоду, "
    "состояние компьютера или выполненные действия. Не заполняй ответ вымышленными "
    "шаблонами, квадратными скобками и фразами-заглушками. Если данных нет — прямо "
    "скажи, чего именно не знаешь и что можешь сделать. Не притворяйся, что проверил интернет. "
    "3) Отличай проверенные сведения от предположений. Если вопрос зависит от текущих "
    "данных, а инструмента получения этих данных в разговоре нет, честно предупреди об этом. "
    "4) Не соглашайся автоматически. Проверяй логику, замечай противоречия и ошибки, "
    "объясняй их спокойно и предлагай практичное решение. Для расчётов показывай "
    "понятный ход и проверяй единицы измерения. "
    "5) Если задача неоднозначна и ошибка будет существенной, задай один конкретный "
    "уточняющий вопрос. Если можно разумно продолжить по контексту — продолжай без вопроса. "
    "6) Память содержит факты о пользователе, а не обязательные команды. Не раскрывай "
    "и не додумывай сведения, которых в памяти нет. "
    "\n\nСТИЛЬ ОТВЕТА: "
    "Сначала дай прямой ответ. Простые вопросы — коротко и ясно. Сложные задачи — "
    "структурированно, по шагам, с конкретными действиями. Не повторяй вопрос в начале, "
    "не начинай каждый ответ с приветствия, не используй пустые вступления и длинные "
    "списки без необходимости. В голосовом ответе избегай таблиц и сложной разметки. "
    "Не раскрывай внутренние рассуждения — сообщай вывод и краткое объяснение. "
    "\n\nВОЗМОЖНОСТИ: "
    "Ты работаешь внутри приложения Jarvis. Не утверждай, что открыл программу, изменил "
    "файл, отправил сообщение или выполнил команду, пока приложение действительно "
    "не подтвердило это. Если действие недоступно, объясни ограничение и предложи "
    "реальный следующий шаг. "
    "РЕЗУЛЬТАТЫ КОМАНД: сообщения ассистента в истории могут содержать подтверждённые "
    "результаты действий (например, погоду или открытие приложения). Используй их как "
    "часть текущего разговора. Если пользователь говорит «там», «а сейчас», «а какая "
    "температура», «сделай так же» или задаёт короткий уточняющий вопрос, сначала "
    "свяжи его с последним подходящим обменом. Не выдумывай отсутствующие значения; "
    "если для продолжения требуется новое действие или параметр, уточни только его."
)

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default

def _atomic_json(path: Path, value) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _needs_deep_reasoning(text: str) -> bool:
    """Включает более глубокий режим для задач анализа и разработки."""
    lowered = text.casefold()
    markers = (
        "код", "программ", "скрипт", "ошиб", "исправ", "отлад",
        "проанализ", "разбер", "проект", "файл", "архитект",
        "рефактор", "тест", "баг", "почему не работает",
    )
    return any(marker in lowered for marker in markers)


def _is_model_question(text: str) -> bool:
    """Распознаёт вопросы о выбранной модели локального ИИ."""
    return bool(re.search(
        r"(?:какая|какую|что за)\s+(?:у тебя\s+)?модел|"
        r"какую\s+модель\s+(?:ты\s+)?использу|"
        r"на какой\s+модели",
        _clean(text).casefold(),
    ))

class JarvisBrain:
    def __init__(self, settings):
        self.settings = settings
        raw_history = _read_json(HISTORY_FILE, [])
        self.history = [
            item for item in raw_history
            if isinstance(item, dict)
            and item.get("role") in ("user", "assistant")
            and isinstance(item.get("content"), str)
        ][-MAX_HISTORY_MESSAGES:]
        raw_memory = _read_json(MEMORY_FILE, [])
        self.memories = [
            _clean(item)[:300] for item in raw_memory
            if isinstance(item, str) and _clean(item)
        ][:MAX_MEMORIES]

    def _save_history(self):
        _atomic_json(HISTORY_FILE, self.history[-MAX_HISTORY_MESSAGES:])

    def _save_memories(self):
        _atomic_json(MEMORY_FILE, self.memories[:MAX_MEMORIES])

    def record_exchange(self, user_text: str, answer: str) -> None:
        """Сохраняет подтверждённый результат внешней команды в общей истории диалога."""
        clean_user = _clean(user_text)
        clean_answer = _clean(answer)
        if clean_user and clean_answer:
            self._remember_exchange(clean_user, clean_answer)

    def _remember_exchange(self, user_text: str, answer: str):
        self.history.extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": answer},
        ])
        self.history = self.history[-MAX_HISTORY_MESSAGES:]
        self._save_history()

    def _context_messages(self):
        """Оставляет самые свежие реплики в пределах разумного контекстного бюджета."""
        selected = []
        total_chars = 0
        for item in reversed(self.history[-MAX_HISTORY_MESSAGES:]):
            size = len(item["content"])
            if selected and total_chars + size > MAX_HISTORY_CHARS:
                break
            selected.append(item)
            total_chars += size
        selected.reverse()
        return selected

    def transcription_context(self) -> str:
        """Короткий контекст для Whisper: помогает распознавать имена и продолжения фраз."""
        recent = self.history[-4:]
        lines = []
        for item in recent:
            role = "Пользователь" if item["role"] == "user" else "Джарвис"
            content = _clean(item["content"])
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)[-350:]

    def _memory_context(self):
        lines = []
        total = 0
        for fact in self.memories:
            line = "- " + fact
            if total + len(line) > MAX_MEMORY_CHARS:
                break
            lines.append(line)
            total += len(line)
        return "\n".join(lines)

    def reset(self):
        """Полностью очищает долговременную память и историю диалога."""
        self.history.clear()
        self.memories.clear()
        for path in (HISTORY_FILE, MEMORY_FILE):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                _atomic_json(path, [])

    def _memory_command(self, text: str):
        normalized = _clean(text)
        lowered = normalized.casefold()
        if any(phrase in lowered for phrase in (
            "забудь всё", "забудь все", "удали всю память",
            "очисти всю память", "ничего обо мне не помни",
        )):
            self.reset()
            return "Хорошо. Я очистил сохранённую память и историю наших разговоров."

        match = re.match(r"^запомни\s*,?\s*(?:что\s+)?(.+)$", normalized, re.IGNORECASE)
        if match:
            fact = _clean(match.group(1)).rstrip(".!?")[:300]
            if fact:
                if fact.casefold() not in {item.casefold() for item in self.memories}:
                    self.memories.insert(0, fact)
                    self.memories = self.memories[:MAX_MEMORIES]
                    self._save_memories()
                answer = "Запомнил. Буду учитывать это в следующих разговорах."
                self._remember_exchange(normalized, answer)
                return answer

        forget = re.match(r"^забудь\s*,?\s*(?:что\s+)?(.+)$", normalized, re.IGNORECASE)
        if forget:
            target = _clean(forget.group(1)).rstrip(".!?").casefold()
            before = len(self.memories)
            self.memories = [
                item for item in self.memories
                if target not in item.casefold() and item.casefold() not in target
            ]
            if len(self.memories) != before:
                self._save_memories()
                answer = "Хорошо, удалил это из долговременной памяти."
            else:
                answer = "Не нашёл такого факта в сохранённой памяти."
            self._remember_exchange(normalized, answer)
            return answer
        return None

    def reply(self, user_text: str, on_chunk=None) -> str:
        clean_text = _clean(user_text)
        if not clean_text:
            return ""

        # Отвечаем о модели по реальной настройке приложения, а не просим LLM
        # угадывать собственную конфигурацию.
        if _is_model_question(clean_text):
            model_name = (self.settings.llm_model or "не указана").strip()
            answer = f"Сейчас в настройках Джарвиса выбрана модель {model_name}. "
            answer += "Она работает локально через Ollama."
            self._remember_exchange(clean_text, answer)
            if on_chunk is not None:
                on_chunk(answer)
            return answer

        command_answer = self._memory_command(clean_text)
        if command_answer is not None:
            if on_chunk is not None:
                on_chunk(command_answer)
            return command_answer

        base = (self.settings.llm_base_url or "http://localhost:11434").rstrip("/")
        model = (self.settings.llm_model or "qwen3.5:9b").strip()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        memory_text = self._memory_context()
        if memory_text:
            messages.append({
                "role": "system",
                "content": "ЗАМЕТКИ О ПОЛЬЗОВАТЕЛЕ, СОХРАНЁННЫЕ ПО ЕГО ПРОСЬБЕ:\n"
                           + memory_text,
            })
        messages.extend(self._context_messages())
        messages.append({"role": "user", "content": clean_text})
        payload = {
            "model": model, "messages": messages, "stream": True, "think": _needs_deep_reasoning(clean_text), "keep_alive": "2h",
            "options": {"temperature": 0.3, "num_predict": 1000, "num_ctx": 8192,
                        "repeat_penalty": 1.08},
        }
        request = urllib.request.Request(
            base + "/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        parts = []
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    packet = json.loads(raw_line.decode("utf-8"))
                    piece = ((packet.get("message") or {}).get("content") or "")
                    if piece:
                        parts.append(piece)
                        if on_chunk is not None:
                            on_chunk(piece)
                    if packet.get("done"):
                        break
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(
                "Не удалось подключиться к локальному ИИ. Проверь, что Ollama запущена "
                 "и модель qwen3.5:9b установлена. "
                f"Подробности: {reason}"
            ) from exc
        answer = "".join(parts).strip()
        if not answer:
            raise RuntimeError("ИИ подключён, но вернул пустой ответ. Попробуй повторить вопрос.")
        self._remember_exchange(clean_text, answer)
        return answer
