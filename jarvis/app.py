"""Основное окно Jarvis AI: голосовой диалог, локальный ИИ и настройки."""
from __future__ import annotations

import ctypes
import threading
import queue
import re
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
        self.root.title("JARVIS AI — персональный ИИ-помощник")
        self.root.geometry("1180x820")
        self.root.minsize(900, 680)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._build()

    def _build(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 14))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", anchor="w")
        tk.Label(brand, text="J.A.R.V.I.S.", bg=BG, fg=CYAN, font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(brand, text="ПЕРСОНАЛЬНЫЙ ИИ-ПОМОЩНИК", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(1, 0))
        status_panel = tk.Frame(header, bg=PANEL, highlightthickness=1, highlightbackground="#1b3a49")
        status_panel.pack(side="right", anchor="e", padx=(12, 0))
        self.status = tk.StringVar(value="ГОТОВ К РАБОТЕ")
        tk.Label(status_panel, textvariable=self.status, bg=PANEL, fg=CYAN, font=("Segoe UI", 9, "bold"), padx=16, pady=11).pack()

        workspace = tk.Frame(self.root, bg=BG)
        workspace.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        voice_panel = tk.Frame(workspace, bg=PANEL, width=270, highlightthickness=1, highlightbackground="#173747")
        voice_panel.pack(side="left", fill="y", padx=(0, 14))
        voice_panel.pack_propagate(False)
        tk.Label(voice_panel, text="ГОЛОСОВОЕ УПРАВЛЕНИЕ", bg=PANEL, fg=CYAN, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(voice_panel, text="Скажите, что нужно сделать", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18)
        self.core = tk.Canvas(voice_panel, width=230, height=190, bg=PANEL, highlightthickness=0, bd=0)
        self.core.pack(pady=(12, 10))
        self._core_phase = 0
        self._animate_core()
        self.listen_button = tk.Button(voice_panel, text="🎙  НАЧАТЬ ГОВОРИТЬ", command=self.listen, font=("Segoe UI", 11, "bold"), bg=GREEN, fg="#ffffff", activebackground="#1b5962", activeforeground="#ffffff", disabledforeground="#a7bec4", relief="flat", bd=0, cursor="hand2", padx=12, pady=15, wraplength=220)
        self.listen_button.pack(fill="x", padx=16, pady=(4, 8))
        self.stop_button = tk.Button(voice_panel, text="■  ОСТАНОВИТЬ ОЗВУЧКУ", command=self.stop_speaking, font=("Segoe UI", 9, "bold"), bg="#542b37", fg="#ffffff", activebackground="#793747", activeforeground="#ffffff", relief="flat", bd=0, cursor="hand2", padx=10, pady=12, state="disabled")
        self.stop_button.pack(fill="x", padx=16, pady=(0, 14))
        tk.Frame(voice_panel, bg="#203b49", height=1).pack(fill="x", padx=16, pady=5)
        tk.Label(voice_panel, text="КАК ЭТО РАБОТАЕТ", bg=PANEL, fg=CYAN, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(8, 5))
        tk.Label(voice_panel, text="1. Нажмите кнопку микрофона.\n2. Скажите свою команду.\n3. Нажмите отправку — Джарвис ответит голосом.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), justify="left", wraplength=225).pack(anchor="w", padx=18, pady=(0, 12))

        chat_panel = tk.Frame(workspace, bg=PANEL, highlightthickness=1, highlightbackground="#173747")
        chat_panel.pack(side="left", fill="both", expand=True)
        chat_header = tk.Frame(chat_panel, bg=PANEL)
        chat_header.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(chat_header, text="ДИАЛОГ", bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Label(chat_header, text="История общения с Джарвисом", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="right")
        history_frame = tk.Frame(chat_panel, bg=PANEL)
        history_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        scrollbar = tk.Scrollbar(history_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.log = tk.Text(history_frame, bg="#0a1a25", fg=TEXT, insertbackground=TEXT, selectbackground="#24515d", relief="flat", wrap="word", font=("Segoe UI", 10), padx=16, pady=14, height=10, borderwidth=0, yscrollcommand=scrollbar.set, spacing1=3, spacing3=7)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.log.yview)
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

        composer = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground="#173747")
        composer.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(composer, text="СООБЩЕНИЕ ДЖАРВИСУ", bg=PANEL, fg=CYAN, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(9, 3))
        input_row = tk.Frame(composer, bg=PANEL)
        input_row.pack(fill="x", padx=12, pady=(0, 12))
        self.text_input = tk.Entry(input_row, bg="#102a38", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        self.text_input.pack(side="left", fill="x", expand=True, ipady=11, padx=(0, 9))
        self.text_input.bind("<Return>", self.send_text)
        self.send_button = tk.Button(input_row, text="ОТПРАВИТЬ  ➤", command=self.send_text, font=("Segoe UI", 9, "bold"), bg=GREEN, fg="#ffffff", activebackground="#1b5962", activeforeground="#ffffff", disabledforeground="#a7bec4", relief="flat", bd=0, cursor="hand2", padx=18, pady=11)
        self.send_button.pack(side="right")

        actions = tk.Frame(self.root, bg=BG)
        actions.pack(fill="x", padx=24, pady=(0, 16))
        def action(label, command, danger=False):
            return tk.Button(actions, text=label, command=command, font=("Segoe UI", 8, "bold"), bg="#18313f" if not danger else "#492a32", fg=TEXT, activebackground="#25495a", activeforeground=TEXT, relief="flat", bd=0, cursor="hand2", padx=11, pady=9)
        self.voice_button = action("ПРОВЕРИТЬ ГОЛОС", self.test_voice)
        self.voice_button.pack(side="left")
        action("КОПИРОВАТЬ ОТВЕТ", self._copy_last_answer).pack(side="left", padx=(7, 0))
        action("КОПИРОВАТЬ ЧАТ", self._copy_all_dialog).pack(side="left", padx=(7, 0))
        action("СОХРАНИТЬ TXT", self._save_dialog).pack(side="left", padx=(7, 0))
        action("ОЧИСТИТЬ ПАМЯТЬ", self.clear_memory, danger=True).pack(side="left", padx=(7, 0))
        action("НАСТРОЙКИ", self.open_settings).pack(side="left", padx=(7, 0))
        action("ВЫХОД", self.root.destroy).pack(side="right")

        if self.brain.history:
            self._append("СИСТЕМА: Предыдущая история диалога восстановлена.")
            for item in self.brain.history[-10:]:
                label = "ВЫ" if item["role"] == "user" else "ДЖАРВИС"
                self._append(f"{label}: {item['content']}")
        else:
            self._append("ДЖАРВИС: Система запущена. Я готов к разговору.")
        self._append("ПОДСКАЗКА: скажите «Запомни, что…», чтобы сохранить важный факт.")

    def _animate_core(self):
        """Плавная анимация ядра без подписи CORE ONLINE."""
        try:
            self.core.delete("pulse")
            phase = self._core_phase % 32
            cx, cy = 115, 88
            for ring in range(3):
                radius = 19 + ring * 15 + ((phase + ring * 7) % 13)
                self.core.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, outline="#1b6572", width=1, tags="pulse")
            self.core.create_oval(cx-31, cy-31, cx+31, cy+31, fill="#102e3b", outline=CYAN, width=2, tags="pulse")
            self.core.create_oval(cx-18, cy-18, cx+18, cy+18, fill="#164b59", outline="#3aaab5", width=1, tags="pulse")
            self.core.create_oval(cx-6, cy-6, cx+6, cy+6, fill=CYAN, outline="", tags="pulse")
            self._core_phase += 1
            self.root.after(100, self._animate_core)
        except tk.TclError:
            pass

    def _reset_tts_stop(self):
        """Совместимость с установленной версией TTS при частичном обновлении."""
        reset = getattr(self.tts, "reset_stop", None)
        if callable(reset):
            reset()
            return
        stop_event = getattr(self.tts, "_stop_event", None)
        clear = getattr(stop_event, "clear", None)
        if callable(clear):
            clear()

    def stop_speaking(self):
        """Прерывает только текущую/ожидающую озвучку, не отменяя вычисление ответа."""
        self._speech_cancelled.set()
        self.tts.stop()
        self.status.set("ОЗВУЧКА ОСТАНОВЛЕНА")
        self.stop_button.configure(state="disabled")

    def _append(self, line: str):
        self.log.insert("end", line + "\n")
        self.log.see("end")

    def _begin_stream_answer(self):
        self.log.insert("end", "ДЖАРВИС: ")
        self.log.see("end")

    def _append_stream_piece(self, piece: str):
        self.log.insert("end", piece)
        self.log.see("end")

    def _finish_stream_answer(self):
        self.log.insert("end", "\n")
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
            self._reset_tts_stop()
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

    def _process_request(self, question: str, on_chunk=None) -> str:
        """Единый маршрут с учётом контекста предыдущей команды."""
        # Короткое уточнение города после ответа о погоде тоже является
        # командой погоды, а не отдельным вопросом к языковой модели.
        history = self.brain.history
        if len(history) >= 2:
            previous_user = history[-2].get("content", "")
            previous_answer = history[-1].get("content", "")
            weather_context = (
                re.search(r"погод|температур", previous_user, re.IGNORECASE)
                or previous_answer.casefold().startswith("сейчас в ")
            )
            city_followup = re.match(
                r"^(?:а\s+)?(?:как\s+)?(?:в|для)\s+(.+?)[?.!]*$",
                question.strip(),
                re.IGNORECASE,
            )
            # Если Джарвис попросил назвать город, пользователь часто
            # отвечает одним словом. Раньше такая реплика уходила в LLM.
            asked_for_city = bool(re.search(
                r"(?:в каком городе|назови город|укажи город)",
                previous_answer,
                re.IGNORECASE,
            ))
            bare_city = question.strip().strip(" .,!?:;") if asked_for_city else ""
            if weather_context and (city_followup or bare_city):
                city = city_followup.group(1).strip() if city_followup else bare_city
                contextual_answer = handle_command("погода в " + city)
                if contextual_answer is not None:
                    self.brain.record_exchange(question, contextual_answer)
                    return contextual_answer

        previous_user_text = ""
        if len(history) >= 2:
            previous_user_text = history[-2].get("content", "")
        answer = handle_command(question, previous_user_text=previous_user_text)
        if answer is not None:
            self.brain.record_exchange(question, answer)
            if on_chunk is not None:
                on_chunk(answer)
            return answer
        return self.brain.reply(question, on_chunk=on_chunk)

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
            recognized = self.asr.transcribe(
                audio, context=self.brain.transcription_context()
            )
            if not recognized:
                self._ui(self.status.set, "РЕЧЬ НЕ РАСПОЗНАНА. ПОПРОБУЙТЕ ЕЩЁ РАЗ.")
                return
            self._ui(self._append, "ВЫ: " + recognized)
            self._ui(self.status.set, "ДУМАЮ И ГОТОВЛЮ ОТВЕТ…")
            speech_queue = queue.Queue()
            sentinel = object()

            def speech_chunks():
                while True:
                    item = speech_queue.get()
                    if item is sentinel:
                        break
                    yield item

            speech_error = []

            def speak_worker():
                try:
                    self.tts.speak_stream(speech_chunks())
                except Exception as exc:
                    speech_error.append(exc)

            self._ui(self._begin_stream_answer)
            speaker = threading.Thread(target=speak_worker, daemon=True)
            if not self._speech_cancelled.is_set():
                speaker.start()

            def on_chunk(piece):
                self._ui(self._append_stream_piece, piece)
                if not self._speech_cancelled.is_set():
                    speech_queue.put(piece)

            try:
                answer = self._process_request(recognized, on_chunk=on_chunk)
            finally:
                speech_queue.put(sentinel)
                self._ui(self._finish_stream_answer)
            self._ui(self._set_last_answer, answer)
            if speaker.is_alive():
                speaker.join()
            if self.tts.last_fallback_error and not self._speech_cancelled.is_set():
                self._ui(
                    self._append,
                    "СИСТЕМА: Edge TTS не вернул аудио; ответ произнесён резервным голосом Windows."
                )
            if speech_error and not self._speech_cancelled.is_set():
                # Потоковая озвучка отдельными короткими фразами иногда
                # получает от Edge TTS ответ без аудио. В таком случае
                # повторно озвучиваем полный ответ одним запросом — это
                # прежний, более надёжный режим.
                stream_error = speech_error[0]
                try:
                    self._ui(self.status.set, "ПЕРЕКЛЮЧАЮСЬ НА НАДЁЖНЫЙ РЕЖИМ ОЗВУЧКИ…")
                    self.tts.speak(answer)
                    self._ui(
                        self._append,
                        "СИСТЕМА: потоковая озвучка временно недоступна; ответ озвучен обычным режимом."
                    )
                except Exception as fallback_error:
                    self._ui(
                        self._append,
                        "ОШИБКА ОЗВУЧКИ: потоковый режим: "
                        + str(stream_error)
                        + " | резервный режим: "
                        + str(fallback_error)
                    )
                    self._ui(self.status.set, "ТЕКСТ ГОТОВ, НО EDGE TTS НЕ ВЕРНУЛ АУДИО")
                    return
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
        self._reset_tts_stop()
        self._set_busy(True, "ПРОВЕРЯЮ НЕЙРОСЕТЕВОЙ РУССКИЙ ГОЛОС…")
        def worker():
            try:
                if not self._speech_cancelled.is_set():
                    self.tts.speak("Здравствуйте. Я Джарвис. Теперь я говорю более естественным голосом.")
                    if self.tts.last_fallback_error:
                        self._ui(
                            self._append,
                            "СИСТЕМА: Edge TTS недоступен; проверка выполнена резервным голосом Windows."
                        )
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
