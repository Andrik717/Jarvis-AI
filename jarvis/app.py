"""Основное окно Jarvis AI: голосовой диалог, локальный ИИ и настройки."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

from .config import load_settings, save_settings
from .audio import Microphone
from .asr import SpeechRecognizer
from .brain import JarvisBrain
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
        self.brain = JarvisBrain(self.settings)
        self.tts = SpeechOutput(self.settings)
        self._busy = False

        self.root = tk.Tk()
        self.root.title("JARVIS AI — голосовой помощник")
        self.root.geometry("940x720")
        self.root.minsize(760, 600)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._build()

    def _build(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(18, 8))
        tk.Label(header, text="J.A.R.V.I.S.", bg=BG, fg=CYAN,
                 font=("Segoe UI", 28, "bold")).pack()
        tk.Label(header, text="ГОЛОСОВОЙ ИИ-ПОМОЩНИК",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10, "bold")).pack(pady=(2, 0))

        status_panel = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                                highlightbackground="#173747")
        status_panel.pack(fill="x", padx=28, pady=(12, 10))
        self.status = tk.StringVar(value="ГОТОВ К РАБОТЕ")
        tk.Label(status_panel, textvariable=self.status, bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 11, "bold"), pady=10).pack()

        self.listen_button = tk.Button(
            self.root, text="🎙   НАЖМИТЕ, ЧТОБЫ ГОВОРИТЬ", command=self.listen,
            font=("Segoe UI", 16, "bold"), bg=GREEN, fg="#ffffff",
            activebackground="#1b5962", activeforeground="#ffffff",
            disabledforeground="#a7bec4", relief="flat", bd=0, cursor="hand2",
            padx=18, pady=20)
        self.listen_button.pack(fill="x", padx=28, pady=(4, 8))

        tk.Label(self.root,
                 text="Говорите после нажатия. Джарвис распознает фразу, ответит и произнесёт ответ.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 8))

        log_frame = tk.Frame(self.root, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=28, pady=8)
        tk.Label(log_frame, text="ИСТОРИЯ ДИАЛОГА", bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 4))
        self.log = tk.Text(log_frame, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                           selectbackground="#24515d", relief="flat", wrap="word",
                           font=("Segoe UI", 11), padx=14, pady=8, height=9, borderwidth=0)
        self.log.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self.log.bind("<Control-c>", self._copy_selection)
        self.log.bind("<Control-C>", self._copy_selection)
        self.log.bind("<Control-Insert>", self._copy_selection)
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Копировать", command=self._copy_selection)
        self.log.bind("<Button-3>", self._show_context_menu)
        if self.brain.history:
            self._append("СИСТЕМА: Предыдущая история диалога восстановлена.")
            for item in self.brain.history[-10:]:
                label = "ВЫ" if item["role"] == "user" else "ДЖАРВИС"
                self._append(f"{label}: {item['content']}")
        else:
            self._append("ДЖАРВИС: Система запущена. Я готов к разговору.")
        self._append("ПОДСКАЗКА: скажите «Запомни, что…», чтобы сохранить важный факт.")

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=28, pady=(8, 18))
        self.voice_button = tk.Button(
            controls, text="ПРОВЕРИТЬ ГОЛОС", command=self.test_voice,
            font=("Segoe UI", 9, "bold"), bg="#18313f", fg=TEXT,
            activebackground="#25495a", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=14, pady=11)
        self.voice_button.pack(side="left")
        tk.Button(
            controls, text="КОПИРОВАТЬ", command=self._copy_selection,
            font=("Segoe UI", 9, "bold"), bg="#18313f", fg=TEXT,
            activebackground="#25495a", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=12, pady=11).pack(side="left", padx=(8, 0))
        tk.Button(
            controls, text="ОЧИСТИТЬ ПАМЯТЬ", command=self.clear_memory,
            font=("Segoe UI", 9, "bold"), bg="#4a2930", fg=TEXT,
            activebackground="#66343d", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=14, pady=11).pack(side="left", padx=(8, 0))
        tk.Button(
            controls, text="НАСТРОЙКИ ИИ", command=self.open_settings,
            font=("Segoe UI", 9, "bold"), bg="#18313f", fg=TEXT,
            activebackground="#25495a", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=14, pady=11).pack(side="left", padx=8)
        tk.Button(
            controls, text="ВЫХОД", command=self.root.destroy,
            font=("Segoe UI", 9, "bold"), bg="#26323a", fg=TEXT,
            activebackground="#3a4b55", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=14, pady=11).pack(side="right")

    def _append(self, line: str):
        self.log.insert("end", line + "\n")
        self.log.see("end")

    def _copy_selection(self, event=None):
        try:
            selected = self.log.get("sel.first", "sel.last")
        except tk.TclError:
            selected = ""
        if selected:
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
            self.status.set("ТЕКСТ СКОПИРОВАН")
        return "break"

    def _show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

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
            text="ОБРАБАТЫВАЮ… ПОДОЖДИТЕ" if busy else "🎙   НАЖМИТЕ, ЧТОБЫ ГОВОРИТЬ")
        self.voice_button.configure(state="disabled" if busy else "normal")

    def _finish_busy(self):
        self._set_busy(False, self.status.get())

    def listen(self):
        if self._busy:
            return
        self._set_busy(True, "СЛУШАЮ… ГОВОРИТЕ В МИКРОФОН")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        try:
            audio = self.mic.record(5.0)
            self._ui(self.status.set, "РАСПОЗНАЮ РЕЧЬ…")
            recognized = self.asr.transcribe(audio)
            if not recognized:
                self._ui(self.status.set, "РЕЧЬ НЕ РАСПОЗНАНА. ПОПРОБУЙТЕ ЕЩЁ РАЗ.")
                return
            self._ui(self._append, "ВЫ: " + recognized)
            self._ui(self.status.set, "ДУМАЮ…")
            answer = self.brain.reply(recognized)
            self._ui(self._append, "ДЖАРВИС: " + answer)
            self._ui(self.status.set, "ОТВЕЧАЮ ГОЛОСОМ…")
            self.tts.speak(answer)
            self._ui(self.status.set, "ГОТОВ. МОЖЕТЕ ГОВОРИТЬ ЕЩЁ РАЗ.")
        except Exception as exc:
            self._ui(self._append, "ОШИБКА: " + str(exc))
            self._ui(self.status.set, "НЕ УДАЛОСЬ ОБРАБОТАТЬ ЗАПРОС — СМОТРИТЕ ЖУРНАЛ")
        finally:
            self._ui(self._finish_busy)

    def clear_memory(self):
        if self._busy:
            return
        confirmed = messagebox.askyesno(
            "Очистка памяти",
            "Удалить сохранённые факты и историю разговоров? Это действие нельзя отменить.",
            parent=self.root,
        )
        if confirmed:
            self.brain.reset()
            self.log.delete("1.0", "end")
            self._append("СИСТЕМА: Память и история очищены. Начинаем с чистого листа.")

    def test_voice(self):
        if self._busy:
            return
        self._set_busy(True, "ПРОВЕРЯЮ НЕЙРОСЕТЕВОЙ РУССКИЙ ГОЛОС…")
        def worker():
            try:
                self.tts.speak("Здравствуйте. Я Джарвис. Теперь я говорю более естественным голосом.")
                self._ui(self.status.set, "ПРОВЕРКА ГОЛОСА ЗАВЕРШЕНА")
            except Exception as exc:
                self._ui(self._append, "ОШИБКА ГОЛОСА: " + str(exc))
                self._ui(self.status.set, "НЕ УДАЛОСЬ ЗАПУСТИТЬ НЕЙРОСЕТЕВОЙ ГОЛОС")
            finally:
                self._ui(self._finish_busy)
        threading.Thread(target=worker, daemon=True).start()

    def open_settings(self):
        if self._busy:
            return
        win = tk.Toplevel(self.root)
        win.title("Настройки Джарвиса")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        frame = tk.Frame(win, bg=BG, padx=22, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="МОЗГ И ГОЛОС", bg=BG, fg=CYAN,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))
        fields = [
            ("Адрес Ollama", self.settings.llm_base_url, "url"),
            ("Модель ИИ", self.settings.llm_model, "model"),
            ("Русский голос", self.settings.tts_voice, "voice"),
        ]
        entries = {}
        for label, value, key in fields:
            tk.Label(frame, text=label, bg=BG, fg=TEXT,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(7, 3))
            entry = tk.Entry(frame, width=46, font=("Segoe UI", 10),
                             bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat")
            entry.insert(0, value)
            entry.pack(fill="x", ipady=7)
            entries[key] = entry

        tk.Label(frame, text="Голоса: ru-RU-SvetlanaNeural (женский), ru-RU-DmitryNeural (мужской).",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=390,
                 justify="left").pack(anchor="w", pady=(10, 12))

        def save():
            self.settings.llm_base_url = entries["url"].get().strip() or "http://localhost:11434"
            self.settings.llm_model = entries["model"].get().strip() or "qwen2.5:3b"
            self.settings.tts_voice = entries["voice"].get().strip() or "ru-RU-SvetlanaNeural"
            self.settings.tts_backend = "edge"
            save_settings(self.settings)
            self.brain.settings = self.settings
            self.tts.settings = self.settings
            self._append("СИСТЕМА: Настройки сохранены.")
            win.destroy()

        tk.Button(frame, text="СОХРАНИТЬ", command=save, bg=GREEN, fg="white",
                  activebackground="#1b5962", relief="flat", padx=18, pady=10,
                  font=("Segoe UI", 10, "bold")).pack(fill="x", pady=(4, 0))

    def run(self):
        self.root.mainloop()


def run_app():
    JarvisWindow().run()
