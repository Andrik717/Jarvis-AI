"""Быстрый локальный ИИ-мозг через Ollama; история диалога хранится в памяти."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

SYSTEM_PROMPT = (
    "Ты Джарвис — умный, спокойный и дружелюбный голосовой помощник пользователя. "
    "Всегда отвечай на русском языке, если пользователь явно не попросил другой. "
    "Говори естественно, как живой собеседник: без канцелярита, длинных вступлений "
    "и повторения вопроса. Для простых вопросов отвечай кратко, для сложных — "
    "структурированно и по делу. Не выдумывай факты и честно говори, если не знаешь. "
    "Не утверждай, что выполнил действие на компьютере, если инструмент этого не сделал."
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
        messages.extend(self.history[-12:])
        messages.append({"role": "user", "content": user_text.strip()})
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.65, "num_predict": 220, "num_ctx": 4096}
        }
        request = urllib.request.Request(
            base + "/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(
                "Не удалось подключиться к локальному ИИ. Установи Ollama, "
                "запусти её и выполни команду: ollama pull qwen2.5:3b. "
                f"Подробности: {reason}"
            ) from exc
        answer = ((data.get("message") or {}).get("content") or "").strip()
        if not answer:
            raise RuntimeError("ИИ подключён, но вернул пустой ответ. Попробуй повторить вопрос.")
        self.history.extend([
            {"role": "user", "content": user_text.strip()},
            {"role": "assistant", "content": answer},
        ])
        self.history = self.history[-16:]
        return answer
