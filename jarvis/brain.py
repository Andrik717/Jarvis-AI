"""Быстрый локальный ИИ-мозг через Ollama с контекстом диалога."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

SYSTEM_PROMPT = (
    "Ты Джарвис — персональный голосовой помощник пользователя, вдохновлённый "
    "образом умного ассистента из фантастики. Ты спокойный, тактичный, "
    "сообразительный, доброжелательный и немного остроумный, но не фамильярный. "
    "Общайся на русском языке, если пользователь не попросил другой язык. "
    "Звучь как естественный собеседник: используй живые короткие фразы, "
    "не начинай каждый ответ с одинакового приветствия, не повторяй вопрос. "
    "Сначала дай прямой ответ, затем необходимые пояснения. Простые вопросы "
    "объясняй кратко; сложные задачи разбивай на понятные шаги. "
    "Учитывай предыдущие реплики и не спрашивай повторно то, что уже известно "
    "из текущего диалога. Если данных не хватает, задай один конкретный вопрос. "
    "Не выдумывай факты, результаты поиска или выполненные действия. "
    "Ты пока не управляешь компьютером напрямую: не говори, что открыл программу, "
    "изменил файл или выполнил действие, если приложение действительно этого не сделало. "
    "Не используй Markdown-таблицы, длинные списки и декоративные символы в "
    "обычных голосовых ответах. Произносимый ответ должен звучать естественно."
)


class JarvisBrain:
    def __init__(self, settings):
        self.settings = settings
        self.history = []

    def reset(self):
        self.history.clear()

    def reply(self, user_text: str) -> str:
        base = (self.settings.llm_base_url or "http://localhost:11434").rstrip("/")
        model = (self.settings.llm_model or "qwen2.5:3b").strip()
        if not user_text.strip():
            return ""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history[-20:])
        messages.append({"role": "user", "content": user_text.strip()})
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.62,
                "num_predict": 300,
                "num_ctx": 4096,
                "repeat_penalty": 1.08,
            },
        }
        request = urllib.request.Request(
            base + "/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(
                "Не удалось подключиться к локальному ИИ. Проверь, что Ollama запущена "
                "и модель qwen2.5:3b установлена. "
                f"Подробности: {reason}"
            ) from exc
        answer = ((data.get("message") or {}).get("content") or "").strip()
        if not answer:
            raise RuntimeError("ИИ подключён, но вернул пустой ответ. Попробуй повторить вопрос.")
        self.history.extend([
            {"role": "user", "content": user_text.strip()},
            {"role": "assistant", "content": answer},
        ])
        self.history = self.history[-20:]
        return answer
