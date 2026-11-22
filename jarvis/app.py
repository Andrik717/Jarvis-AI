"""Основное окно Jarvis AI: голосовой диалог, локальный ИИ и настройки."""
from __future__ import annotations

import ctypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from .config import load_settings, save_settings
from .audio import Microphone
from .asr import SpeechRecognizer
from .brain import JarvisBrain
from .tts import SpeechOutput
from .pc_control import handle_command

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
        self._recording = False
        self._speech_cancelled = threading.Event()
        self.last_answer = ""

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
        self.core = tk.Canvas(header, width=210, height=94, bg=BG,
                              highlightthickness=0, bd=0)
        self.core.pack(pady=(5, 0))
        self._core_phase = 0
        self._animate_core()

        status_panel = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                                highlightbackground="#173747")
        status_panel.pack(fill="x", padx=28, pady=(12, 10))
        self.status = tk.StringVar(value="ГОТОВ К РАБОТЕ")
        tk.Label(status_panel, textvariable=self.status, bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 11, "bold"), pady=10).pack()

        voice_row = tk.Frame(self.root, bg=BG)
        voice_row.pack(fill="x", padx=28, pady=(4, 8))
        self.listen_button = tk.Button(
            voice_row, text="🎙   НАЖМИТЕ, ЧТОБЫ ГОВОРИТЬ", command=self.listen,
            font=("Segoe UI", 16, "bold"), bg=GREEN, fg="#ffffff",
            activebackground="#1b5962", activeforeground="#ffffff",
            disabledforeground="#a7bec4", relief="flat", bd=0, cursor="hand2",
            padx=18, pady=20)
        self.listen_button.pack(side="left", fill="x", expand=True)
        self.stop_button = tk.Button(
            voice_row, text="■  СТОП", command=self.stop_speaking,
            font=("Segoe UI", 12, "bold"), bg="#642b36", fg="#ffffff",
            activebackground="#8b3545", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=22, pady=20,
            state="disabled")
        self.stop_button.pack(side="right", padx=(10, 0))

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
        # Слушаем все нажатия: на Windows Tk по-разному описывает Ctrl+C
        # в зависимости от активной раскладки клавиатуры.
        self.root.bind_all("<KeyPress>", self._copy_on_ctrl_key, add="+")
        self.root.bind_all("<Control-Insert>", self._copy_selection, add="+")
        self.log.bind("<Control-Insert>", self._copy_selection, add="+")
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Копировать выделенное", command=self._copy_selection)
        self.context_menu.add_command(label="Копировать весь диалог", command=self._copy_all_dialog)
        self.context_menu.add_command(label="Копировать последний ответ Джарвиса", command=self._copy_last_answer)
        self.log.bind("<Button-3>", self._show_context_menu)
        self.log.bind("<Control-a>", self._select_all)
        self.log.bind("<Control-A>", self._select_all)

        # Отдельный текстовый ввод: микрофон запускается только кнопкой выше.
        text_frame = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                              highlightbackground="#173747")
        text_frame.pack(fill="x", padx=28, pady=(0, 8))
        tk.Label(text_frame, text="ТЕКСТОВАЯ КОНСОЛЬ — НАПИШИТЕ ДЖАРВИСУ",
                 bg=PANEL, fg=CYAN, font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(8, 4))
        input_row = tk.Frame(text_frame, bg=PANEL)
        input_row.pack(fill="x", padx=10, pady=(0, 10))
        self.text_input = tk.Entry(
            input_row, bg="#102a38", fg=TEXT, insertbackground=TEXT,
            relief="flat", font=("Segoe UI", 11),
        )
        self.text_input.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 8))
        self.text_input.bind("<Return>", self.send_text)
        self.send_button = tk.Button(
            input_row, text="ОТПРАВИТЬ", command=self.send_text,
            font=("Segoe UI", 9, "bold"), bg=GREEN, fg="#ffffff",
            activebackground="#1b5962", activeforeground="#ffffff",
            disabledforeground="#a7bec4", relief="flat", bd=0,
            cursor="hand2", padx=18, pady=10,
        )
        self.send_button.pack(side="right")
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
            controls, text="КОПИРОВАТЬ ОТВЕТ", command=self._copy_last_answer,
            font=("Segoe UI", 9, "bold"), bg="#18313f", fg=TEXT,
            activebackground="#25495a", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=12, pady=11).pack(side="left", padx=(8, 0))
        tk.Button(
            controls, text="КОПИРОВАТЬ ВЕСЬ ЧАТ", command=self._copy_all_dialog,
            font=("Segoe UI", 9, "bold"), bg="#18313f", fg=TEXT,
            activebackground="#25495a", activeforeground=TEXT,
            relief="flat", bd=0, cursor="hand2", padx=12, pady=11).pack(side="left", padx=(8, 0))
        tk.Button(
            controls, text="СОХРАНИТЬ ЧАТ TXT", command=self._save_dialog,
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

    def _animate_core(self):
        """Небольшая анимация ядра; работает только в главном Tk-потоке."""
        try:
            self.core.delete("pulse")
            phase = self._core_phase % 24
            for ring in range(3):
                radius = 17 + ring * 12 + ((phase + ring * 5) % 12)
                x0, y0 = 105 - radius, 45 - radius
                x1, y1 = 105 + radius, 45 + radius
                self.core.create_oval(x0, y0, x1, y1, outline="#1b6572",
                                      width=1, tags="pulse")
            self.core.create_oval(91, 31, 119, 59, fill="#123d4b",
                                  outline=CYAN, width=2, tags="pulse")
            self.core.create_oval(100, 40, 110, 50, fill=CYAN,
                                  outline="", tags="pulse")
            self.core.create_text(105, 83, text="J.A.R.V.I.S.  •  CORE ONLINE",
                                  fill=MUTED, font=("Segoe UI", 8, "bold"), tags="pulse")
            self._core_phase += 1
            self.root.after(90, self._animate_core)
        except tk.TclError:
            pass

    def stop_speaking(self):
        """Прерывает только текущую/ожидающую озвучку, не отменяя вычисление ответа."""
        self._speech_cancelled.set()
        self.tts.stop()
        self.status.set("ОЗВУЧКА ОСТАНОВЛЕНА")
        self.stop_button.configure(state="disabled")

    def _append(self, line: str):
        self.log.insert("end", line + "\n")
        self.log.see("end")

    def _put_clipboard(self, text: str):
        if not text or not text.strip():
            self.status.set("НЕТ ТЕКСТА ДЛЯ КОПИРОВАНИЯ")
            return False

        # Сначала используем штатный буфер Tkinter: он корректно работает с Unicode.
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            self.root.update()
            copied = self.root.clipboard_get()
            if copied != text:
                raise tk.TclError("Проверка буфера обмена не пройдена")
        except tk.TclError as first_error:
            # Резервный прямой способ для Windows.
            if __import__("os").name != "nt":
                self.status.set("ОШИБКА КОПИРОВАНИЯ: " + str(first_error)[:60])
                return False
            try:
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                handle_type = ctypes.c_void_p
                user32.OpenClipboard.argtypes = [handle_type]
                user32.OpenClipboard.restype = ctypes.c_bool
                user32.EmptyClipboard.restype = ctypes.c_bool
                user32.SetClipboardData.argtypes = [ctypes.c_uint, handle_type]
                user32.SetClipboardData.restype = handle_type
                user32.CloseClipboard.restype = ctypes.c_bool
                kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
                kernel32.GlobalAlloc.restype = handle_type
                kernel32.GlobalLock.argtypes = [handle_type]
                kernel32.GlobalLock.restype = handle_type
                kernel32.GlobalUnlock.argtypes = [handle_type]
                kernel32.GlobalUnlock.restype = ctypes.c_bool
                kernel32.GlobalFree.argtypes = [handle_type]
                kernel32.GlobalFree.restype = handle_type

                memory = None
                opened = False
                try:
                    if not user32.OpenClipboard(None):
                        raise OSError("Буфер обмена занят")
                    opened = True
                    if not user32.EmptyClipboard():
                        raise OSError("Не удалось очистить буфер")
                    # CF_UNICODETEXT требует настоящий завершающий UTF-16 NUL.
                    data = (text + "\0").encode("utf-16-le")
                    memory = kernel32.GlobalAlloc(0x0002, len(data))
                    if not memory:
                        raise OSError("Не удалось выделить память")
                    pointer = kernel32.GlobalLock(memory)
                    if not pointer:
                        raise OSError("Не удалось получить память")
                    ctypes.memmove(pointer, data, len(data))
                    kernel32.GlobalUnlock(memory)
                    if not user32.SetClipboardData(13, memory):
                        raise OSError("Windows не принял текст")
                    memory = None
                finally:
                    if opened:
                        user32.CloseClipboard()
                    if memory:
                        kernel32.GlobalFree(memory)
            except Exception as exc:
                self.status.set("НЕ УДАЛОСЬ СКОПИРОВАТЬ: " + str(exc)[:55])
                return False

        self.status.set("СКОПИРОВАНО! ВСТАВЬТЕ ТЕКСТ КЛАВИШАМИ CTRL+V")
        return True

    def _copy_on_ctrl_key(self, event=None):
        if event is None:
            return None

        keysym = str(getattr(event, "keysym", "")).lower()
        char = str(getattr(event, "char", "")).lower()
        keycode = getattr(event, "keycode", 0)
        state = getattr(event, "state", 0)

        # На Windows проверяем состояние Ctrl напрямую: Tk может менять
        # state/keysym при переключении русской и английской раскладки.
        ctrl_down = bool(state & 0x4)
        if not ctrl_down:
            try:
                ctrl_down = bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000)
            except Exception:
                pass

        # В русской раскладке физическая клавиша C может приходить как
        # Cyrillic_es, «с» или иной keysym; учитываем также символ и VK-код.
        is_c = (
            keysym in ("c", "с", "cyrillic_es")
            or char in ("c", "с")
            or keycode == 67
        )
        if ctrl_down and is_c:
            return self._copy_selection(event)
        return None

    def _copy_selection(self, event=None):
        # Событие клавиатуры надёжнее focus_get(): Tk иногда оставляет фокус
        # на другом элементе, хотя выделение видно в истории диалога.
        candidates = []
        event_widget = getattr(event, "widget", None) if event is not None else None
        if event_widget is not None:
            candidates.append(event_widget)
        try:
            focused = self.root.focus_get()
        except tk.TclError:
            focused = None
        if focused is not None and focused not in candidates:
            candidates.append(focused)
        if self.log not in candidates:
            candidates.append(self.log)

        selected = ""
        for widget in candidates:
            try:
                if isinstance(widget, tk.Text):
                    ranges = widget.tag_ranges("sel")
                    if len(ranges) >= 2:
                        selected = widget.get(ranges[0], ranges[1])
                elif isinstance(widget, tk.Entry):
                    first = widget.index("sel.first")
                    last = widget.index("sel.last")
                    selected = widget.get()[first:last]
            except (tk.TclError, AttributeError):
                selected = ""
            if selected:
                break

        if selected:
            self._put_clipboard(selected)
            return "break"
        # Не блокируем штатное поведение Ctrl+C, если выделения нет.
        return None

    def _copy_all_dialog(self):
        self._put_clipboard(self.log.get("1.0", "end-1c"))

    def _select_all(self, event=None):
        self.log.tag_add("sel", "1.0", "end-1c")
        self.log.mark_set("insert", "end-1c")
        self.log.see("insert")
        return "break"

    def _copy_last_answer(self):
        answer = self.last_answer.strip()
        if not answer:
            for line in reversed(self.log.get("1.0", "end-1c").splitlines()):
                if line.startswith("ДЖАРВИС: "):
                    answer = line[len("ДЖАРВИС: "):].strip()
                    break
        self._put_clipboard(answer)

    def _save_dialog(self):
        content = self.log.get("1.0", "end-1c")
        if not content.strip():
            self.status.set("ИСТОРИЯ ДИАЛОГА ПУСТА")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Сохранить переписку Джарвиса",
            defaultextension=".txt",
            filetypes=[("Текстовый файл", "*.txt")],
            initialfile="dialog_jarvis.txt",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig") as file:
                file.write(content)
            self.status.set("ПЕРЕПИСКА СОХРАНЕНА В TXT")
        except OSError as exc:
            messagebox.showerror("Ошибка сохранения", str(exc), parent=self.root)

    def _set_last_answer(self, answer: str):
        self.last_answer = answer

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
        self.send_button.configure(state="disabled" if busy else "normal")
        self.text_input.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")

    def _finish_busy(self):
        self._set_busy(False, self.status.get())

    def listen(self):
        """Переключает микрофон: начать запись или отправить текущую."""
        if self._busy:
            return
        if self._recording:
            self._send_recording()
            return
        try:
            self.mic.start_recording()
            self._recording = True
            self.status.set("ИДЁТ ЗАПИСЬ… НАЖМИТЕ «ОТПРАВИТЬ», КОГДА ЗАКОНЧИТЕ")
            self.listen_button.configure(
                text="➤  ОТПРАВИТЬ ГОЛОСОВОЕ",
                bg="#17616a",
                activebackground="#21808a",
            )
        except Exception as exc:
            self._recording = False
            self.status.set("НЕ УДАЛОСЬ ВКЛЮЧИТЬ МИКРОФОН")
            self._append("ОШИБКА МИКРОФОНА: " + str(exc))

    def _send_recording(self):
        """Останавливает запись по нажатию отправки и передаёт аудио на обработку."""
        if not self._recording or self._busy:
            return
        try:
            audio = self.mic.stop_recording()
            self._recording = False
            if audio.size == 0:
                self.status.set("ЗАПИСЬ ПУСТАЯ. ПОПРОБУЙТЕ ЕЩЁ РАЗ.")
                self.listen_button.configure(
                    text="🎙   НАЖМИТЕ, ЧТОБЫ ГОВОРИТЬ",
                    bg=GREEN,
                    activebackground="#1b5962",
                )
                return
            self._speech_cancelled.clear()
            self.tts.reset_stop()
            self._set_busy(True, "ОТПРАВЛЯЮ ЗАПИСЬ НА РАСПОЗНАВАНИЕ…")
            threading.Thread(
                target=self._listen_worker, args=(audio,), daemon=True
            ).start()
        except Exception as exc:
            self._recording = False
            self.status.set("НЕ УДАЛОСЬ ОТПРАВИТЬ ГОЛОСОВОЕ СООБЩЕНИЕ")
            self._append("ОШИБКА ЗАПИСИ: " + str(exc))
            self.listen_button.configure(
                state="normal",
                text="🎙   НАЖМИТЕ, ЧТОБЫ ГОВОРИТЬ",
                bg=GREEN,
                activebackground="#1b5962",
            )

    def send_text(self, event=None):
        """Отправляет набранный текст, не включая микрофон и озвучку."""
        if self._busy:
            return "break"
        question = self.text_input.get().strip()
        if not question:
            return "break"
        self.text_input.delete(0, "end")
        self._append("ВЫ: " + question)
        self._set_busy(True, "ОБРАБАТЫВАЮ ТЕКСТОВЫЙ ЗАПРОС…")
        threading.Thread(target=self._text_worker, args=(question,), daemon=True).start()
        return "break"

    def _process_request(self, question: str) -> str:
        """Единый маршрут: команда или локальный ИИ; оба результата входят в контекст."""
        answer = handle_command(question)
        if answer is not None:
            self.brain.record_exchange(question, answer)
            return answer
        return self.brain.reply(question)

    def _text_worker(self, question: str):
        try:
            answer = self._process_request(question)
            self._ui(self._append, "ДЖАРВИС: " + answer)
            self._ui(self._set_last_answer, answer)
            self._ui(self.status.set, "ГОТОВ. МОЖЕТЕ НАПИСАТЬ СЛЕДУЮЩИЙ ВОПРОС.")
        except Exception as exc:
            self._ui(self._append, "ОШИБКА: " + str(exc))
            self._ui(self.status.set, "НЕ УДАЛОСЬ ОБРАБОТАТЬ ТЕКСТОВЫЙ ЗАПРОС")
        finally:
            self._ui(self._finish_busy)

    def _listen_worker(self, audio):
        try:
            self._ui(self.status.set, "РАСПОЗНАЮ РЕЧЬ…")
            recognized = self.asr.transcribe(audio)
            if not recognized:
                self._ui(self.status.set, "РЕЧЬ НЕ РАСПОЗНАНА. ПОПРОБУЙТЕ ЕЩЁ РАЗ.")
                return
            self._ui(self._append, "ВЫ: " + recognized)
            self._ui(self.status.set, "ДУМАЮ…")
            answer = self._process_request(recognized)
            self._ui(self._append, "ДЖАРВИС: " + answer)
            self._ui(self._set_last_answer, answer)
            if not self._speech_cancelled.is_set():
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
        self._speech_cancelled.clear()
        self.tts.reset_stop()
        self._set_busy(True, "ПРОВЕРЯЮ НЕЙРОСЕТЕВОЙ РУССКИЙ ГОЛОС…")
        def worker():
            try:
                if not self._speech_cancelled.is_set():
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

        tk.Label(frame, text="Голос Джарвиса по умолчанию: ru-RU-DmitryNeural (мужской). Можно указать другой голос Edge TTS.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=390,
                 justify="left").pack(anchor="w", pady=(10, 12))

        def save():
            self.settings.llm_base_url = entries["url"].get().strip() or "http://localhost:11434"
            self.settings.llm_model = entries["model"].get().strip() or "qwen3.5:9b"
            self.settings.tts_voice = entries["voice"].get().strip() or "ru-RU-DmitryNeural"
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
