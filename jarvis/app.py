"""Небольшой desktop MVP: запись по кнопке, локальная расшифровка и озвучка."""
from __future__ import annotations
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from .config import load_settings
from .audio import Microphone
from .asr import SpeechRecognizer
from .tts import SpeechOutput

class JarvisWindow:
    def __init__(self):
        self.settings = load_settings()
        self.mic = Microphone()
        self.asr = SpeechRecognizer(self.settings)
        self.tts = SpeechOutput(self.settings)
        self.root = tk.Tk()
        self.root.title("JARVIS AI")
        self.root.geometry("760x520")
        self.root.minsize(620, 420)
        self.root.configure(bg="#07131d")
        self._build()

    def _build(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 11), padding=10)
        header = tk.Label(self.root, text="J.A.R.V.I.S.", bg="#07131d", fg="#62e6ee", font=("Segoe UI", 24, "bold"))
        header.pack(pady=(22, 4))
        tk.Label(self.root, text="РУССКИЙ ГОЛОСОВОЙ АССИСТЕНТ · LOCAL MVP", bg="#07131d", fg="#7e9eac", font=("Segoe UI", 9)).pack()
        self.status = tk.StringVar(value="Готов к работе")
        tk.Label(self.root, textvariable=self.status, bg="#07131d", fg="#62e6ee", font=("Segoe UI", 11)).pack(pady=16)
        self.log = tk.Text(self.root, bg="#0d202d", fg="#d6edf2", insertbackground="white", relief="flat", wrap="word", font=("Segoe UI", 11), padx=14, pady=12)
        self.log.pack(fill="both", expand=True, padx=24, pady=8)
        self.log.insert("end", "JARVIS: Система запущена. Нажмите «Слушать», произнесите фразу и дождитесь расшифровки.\n")
        self.log.configure(state="disabled")
        bar = tk.Frame(self.root, bg="#07131d")
        bar.pack(fill="x", padx=24, pady=18)
        ttk.Button(bar, text="🎙  Слушать 5 секунд", command=self.listen).pack(side="left")
        ttk.Button(bar, text="Проверить голос", command=self.test_voice).pack(side="left", padx=10)
        ttk.Button(bar, text="Выход", command=self.root.destroy).pack(side="right")

    def _append(self, line: str):
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _ui(self, fn, *args):
        self.root.after(0, lambda: fn(*args))

    def listen(self):
        self.status.set("Слушаю… говорите после нажатия")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        try:
            audio = self.mic.record(5.0)
            self._ui(self.status.set, "Распознаю речь…")
            text = self.asr.transcribe(audio)
            if text:
                self._ui(self._append, "ВЫ: " + text)
                self._ui(self.status.set, "Распознавание завершено")
            else:
                self._ui(self.status.set, "Речь не обнаружена — попробуйте ещё раз")
        except Exception as exc:
            self._ui(self.status.set, "Ошибка микрофона или распознавания")
            self._ui(messagebox.showerror, "Jarvis AI", str(exc))

    def test_voice(self):
        def worker():
            try:
                self.tts.speak("Привет. Я Джарвис. Голосовая система готова к работе.")
                self._ui(self.status.set, "Проверка голоса запущена")
            except Exception as exc:
                self._ui(messagebox.showerror, "Синтез речи", str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        self.root.mainloop()

def run_app():
    JarvisWindow().run()
