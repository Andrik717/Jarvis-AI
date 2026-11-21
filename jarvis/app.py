"""Основное окно Jarvis AI: крупные видимые элементы управления."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

from .config import load_settings
from .audio import Microphone
from .asr import SpeechRecognizer
from .tts import SpeechOutput


BG = "#07131d"
PANEL = "#0d202d"
CYAN = "#62e6ee"
TEXT = "#e7f5f7"
MUTED = "#8aa8b5"
GREEN = "#123d45"


class JarvisWindow:
    def __init__(self):
        self.settings = load_settings()
        self.mic = Microphone()
        self.asr = SpeechRecognizer(self.settings)
        self.tts = SpeechOutput(self.settings)
        self._busy = False

        self.root = tk.Tk()
        self.root.title("JARVIS AI — голосовой помощник")
        self.root.geometry("900x680")
        self.root.minsize(720, 560)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._build()

    def _build(self):
        # Используем обычные tk.Button: они заметнее и предсказуемее,
        # чем системные ttk-кнопки на разных темах Windows.
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 8))

        tk.Label(
            header, text="J.A.R.V.I.S.", bg=BG, fg=CYAN,
            font=("Segoe UI", 28, "bold")
        ).pack()
        tk.Label(
            header, text="РУССКИЙ ГОЛОСОВОЙ ПОМОЩНИК",
            bg=BG, fg=MUTED, font=("Segoe UI", 10, "bold")
        ).pack(pady=(2, 0))

        status_panel = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                                highlightbackground="#173747")
        status_panel.pack(fill="x", padx=28, pady=(14, 12))
        self.status = tk.StringVar(value="ГОТОВ К РАБОТЕ")
        tk.Label(
            status_panel, textvariable=self.status, bg=PANEL, fg=CYAN,
            font=("Segoe UI", 12, "bold"), pady=12
        ).pack()

        # Главная кнопка находится отдельно и занимает всю ширину.
        self.listen_button = tk.Button(
            self.root,
            text="🎙   НАЖМИТЕ, ЧТОБЫ ГОВОРИТЬ",
            command=self.listen,
            font=("Segoe UI", 16, "bold"),
            bg=GREEN, fg="#ffffff", activebackground="#1b5962",
            activeforeground="#ffffff", disabledforeground="#a7bec4",
            relief="flat", bd=0, cursor="hand2",
            padx=18, pady=22
        )
        self.listen_button.pack(fill="x", padx=28, pady=(4, 12))

        hint = tk.Label(
            self.root,
            text="После нажатия говорите в микрофон в течение 5 секунд.",
            bg=BG, fg=MUTED, font=("Segoe UI", 10)
        )
        hint.pack(pady=(0, 8))

        log_frame = tk.Frame(self.root, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=28, pady=8)

        tk.Label(
            log_frame, text="ЖУРНАЛ ДИАЛОГА", bg=PANEL, fg=CYAN,
            font=("Segoe UI", 9, "bold"), anchor="w"
        ).pack(fill="x", padx=14, pady=(12, 4))

        self.log = tk.Text(
            log_frame, bg=PANEL, fg=TEXT, insertbackground=TEXT,
            selectbackground="#24515d", relief="flat", wrap="word",
            font=("Segoe UI", 11), padx=14, pady=8, height=8,
            borderwidth=0
        )
        self.log.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self._append("JARVIS: Система запущена. Нажмите большую кнопку выше и произнесите фразу.")

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=28, pady=(10, 22))

        self.voice_button = tk.Button(
            controls, text="ПРОВЕРИТЬ ГОЛОС", command=self.test_voice,
            font=("Segoe UI", 10, "bold"), bg="#18313f", fg=TEXT,
            activebackground="#25495a", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=18, pady=12
        )
        self.voice_button.pack(side="left")

        tk.Button(
            controls, text="ВЫХОД", command=self.root.destroy,
            font=("Segoe UI", 10, "bold"), bg="#26323a", fg=TEXT,
            activebackground="#3a4b55", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=18, pady=12
        ).pack(side="right")

    def _append(self, line: str):
        self.log.insert("end", line + "\n")
        self.log.see("end")

    def _ui(self, fn, *args):
        try:
            self.root.after(0, lambda: fn(*args))
        except tk.TclError:
            pass

    def _set_busy(self, busy: bool, status: str):
        self._busy = busy
        self.status.set(status)
        self.listen_button.configure(
            state="disabled" if busy else "normal",
            text="РАБОТАЮ… ПОЖАЛУЙСТА, ПОДОЖДИТЕ" if busy
                 else "🎙   НАЖМИТЕ, ЧТОБЫ ГОВОРИТЬ"
        )
        self.voice_button.configure(state="disabled" if busy else "normal")

    def _finish_busy(self):
        # Вызывается только в главном потоке Tkinter.
        self._set_busy(False, self.status.get())

    def listen(self):
        if self._busy:
            return
        self._set_busy(True, "СЛУШАЮ… ГОВОРИТЕ В МИКРОФОН")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        try:
            audio = self.mic.record(5.0)
            self._ui(self.status.set, "РАСПОЗНАЮ РЕЧЬ… ПЕРВЫЙ ЗАПУСК МОЖЕТ ЗАНЯТЬ ВРЕМЯ")
            recognized = self.asr.transcribe(audio)
            if recognized:
                self._ui(self._append, "ВЫ: " + recognized)
                self._ui(self.status.set, "ГОТОВО. МОЖЕТЕ ГОВОРИТЬ ЕЩЁ РАЗ.")
            else:
                self._ui(self.status.set, "РЕЧЬ НЕ ОБНАРУЖЕНА. ПОПРОБУЙТЕ ЕЩЁ РАЗ.")
        except Exception as exc:
            self._ui(self._append, "ОШИБКА: " + str(exc))
            self._ui(messagebox.showerror, "Jarvis AI — ошибка", str(exc))
            self._ui(self.status.set, "ПРОВЕРЬТЕ МИКРОФОН И НАСТРОЙКИ")
        finally:
            self._ui(self._finish_busy)

    def test_voice(self):
        if self._busy:
            return
        self._set_busy(True, "ПРОВЕРЯЮ РУССКИЙ ГОЛОС…")

        def worker():
            try:
                self.tts.speak("Привет. Я Джарвис. Проверка русского голоса прошла.")
                self._ui(self.status.set, "КОМАНДА ОЗВУЧИВАНИЯ ОТПРАВЛЕНА")
            except Exception as exc:
                self._ui(self._append, "ОШИБКА ГОЛОСА: " + str(exc))
                self._ui(messagebox.showerror, "Синтез речи", str(exc))
                self._ui(self.status.set, "НЕ УДАЛОСЬ ЗАПУСТИТЬ ГОЛОС")
            finally:
                self._ui(self._set_busy, False, self.status.get())

        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        self.root.mainloop()


def run_app():
    JarvisWindow().run()
