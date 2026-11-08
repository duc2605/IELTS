"""Word Runner IELTS: native desktop typing game for Ubuntu and Windows."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "words.json"
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or (os.environ.get("LOCALAPPDATA", str(Path.home())) if os.name == "nt" else Path.home() / ".local" / "share"))
STATE_DIR = DATA_HOME / "word-runner-ielts"
STATE_FILE = STATE_DIR / "state.json"
CACHE_DIR = STATE_DIR / "audio"
BASE_SECONDS = 15
STAGE_COUNT = 20
SAVE_VERSION = 2
SPEEDS = (1.0, 1.15, 1.3, 1.5)
REVIEW_DELAYS = (600, 86400, 259200, 604800, 1209600, 2592000)
BOOKS = {"all": "Cả 4 quyển", "1": "Elementary", "2": "Pre-Intermediate", "3": "Upper-Intermediate", "4": "Advanced"}
MODES = {"copy": "1 · Nhìn và gõ lại", "recall": "2 · Nhớ và viết", "review": "3 · Ôn theo lịch"}
BG = "#071528"
PANEL = "#112941"
EDGE = "#3d6481"
TEXT = "#e9f8ff"
MUTED = "#a6c4d2"
MINT = "#79ead7"
CORAL = "#ff9b79"


def normalized(text: str) -> str:
    text = re.sub(r"[^\w\s]", "", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def word_key(word: dict) -> str:
    return word.get("_key") or f"{word['book']}:{word['en'].strip().casefold()}"


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class Narrator:
    """Speak in a worker thread so synthesis never freezes the game window."""

    def __init__(self):
        self.generation = 0
        self.process = None
        self.lock = threading.Lock()
        self.voice_region = "en-GB"
        self.vi_voice = "Nữ"
        self.sound_on = True
        self.vi_on = True
        self.status = ""

    def stop(self):
        with self.lock:
            self.generation += 1
            process = self.process
            self.process = None
        if process and process.poll() is None:
            process.kill()

    def speak_pair(self, word: dict):
        self.stop()
        if not self.sound_on:
            return
        with self.lock:
            generation = self.generation
        threading.Thread(target=self._speak_pair, args=(word, generation), daemon=True).start()

    def _speak_pair(self, word: dict, generation: int):
        self._speak(word["en"], "en", generation)
        if self.vi_on and self._current(generation):
            time.sleep(0.2)
            self._speak(word["vi"], "vi", generation)

    def _current(self, generation: int) -> bool:
        with self.lock:
            return generation == self.generation and self.sound_on

    def _speak(self, text: str, language: str, generation: int):
        if not text or not self._current(generation):
            return
        voice = (
            "en-GB-SoniaNeural" if self.voice_region == "en-GB"
            else "en-US-JennyNeural"
        ) if language == "en" else (
            "vi-VN-HoaiMyNeural" if self.vi_voice == "Nữ"
            else "vi-VN-NamMinhNeural"
        )
        player = shutil.which("ffplay")
        if player:
            try:
                import edge_tts

                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:24]
                audio = CACHE_DIR / f"{digest}.mp3"
                if not audio.is_file():
                    asyncio.run(edge_tts.Communicate(text, voice, rate="-8%").save(str(audio)))
                if not self._current(generation):
                    return
                self._play([player, "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio)], generation)
                return
            except Exception:
                self.status = "Giọng trực tuyến không khả dụng; dùng giọng hệ thống."
        system = shutil.which("spd-say")
        if system:
            self._play([system, "-w", "-l", "en" if language == "en" else "vi", text], generation)
        else:
            self.status = "Cài edge-tts và ffmpeg để bật phát âm."

    def _play(self, command: list[str], generation: int):
        try:
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.lock:
                if generation != self.generation:
                    process.kill()
                    return
                self.process = process
            process.wait()
            with self.lock:
                if self.process is process:
                    self.process = None
        except OSError:
            self.status = "Không phát được âm thanh trên máy này."


class WordRunner:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Word Runner IELTS · Desktop")
        self.root.configure(bg=BG)
        self.root.geometry("1080x760")
        self.root.minsize(900, 650)
        self.words = read_json(DATA_FILE, [])
        if not self.words:
            messagebox.showerror("Thiếu dữ liệu", f"Không đọc được {DATA_FILE}")
            root.destroy()
            return
        key_counts = {}
        for word in self.words:
            base_key = word_key(word)
            key_counts[base_key] = key_counts.get(base_key, 0) + 1
            word["_key"] = base_key if key_counts[base_key] == 1 else f"{base_key}#{key_counts[base_key]}"
        self.by_key = {word_key(w): w for w in self.words if w.get("en") and w.get("vi")}
        self.state = read_json(STATE_FILE, {})
        self.learned = set(self.state.get("learned", []))
        self.reviews = self.state.get("reviews", {})
        self.rankings = self.state.get("rankings", [])
        self.daily = self.state.get("daily", {})
        self.book = self.state.get("book", "all")
        self.mode = self.state.get("mode", "copy")
        if self.book not in BOOKS:
            self.book = "all"
        if self.mode not in MODES:
            self.mode = "copy"
        if self.state.get("save_version") == SAVE_VERSION:
            self.stage = max(1, min(STAGE_COUNT, int(self.state.get("stage", 1))))
        else:
            pool_size = sum(1 for w in self.words if self.book == "all" or str(w["book"]) == self.book)
            learned_count = sum(1 for w in self.words if (self.book == "all" or str(w["book"]) == self.book) and word_key(w) in self.learned)
            self.stage = min(STAGE_COUNT, 1 + learned_count * STAGE_COUNT // max(1, pool_size))
        self.cycle = max(1, int(self.state.get("cycle", 1)))
        self.total = max(0, int(self.state.get("total", 0)))
        self.global_wave = max(0, int(self.state.get("global_wave", 0)))
        self.killed = max(0, int(self.state.get("killed", 0)))
        self.stage_goal = max(0, int(self.state.get("stage_goal", 0)))
        self.speed_index = max(0, min(len(SPEEDS) - 1, int(self.state.get("speed_index", 0))))
        self.queue = ([k for k in self.state.get("active", []) + self.state.get("queue", []) if k in self.by_key]
                      if self.state.get("save_version") == SAVE_VERSION else [])
        self.active: list[dict] = []
        self.wave_words: list[str] = []
        self.wave_hits: set[str] = set()
        self.target = None
        self.paused = bool(self.state.get("paused", False))
        self.transitioning = False
        self.book_finished = False
        self.remaining = 0.0
        self.deadline = 0.0
        self.wave_duration = 0.0
        self.pending_job = None
        self.victory_job = None
        self.last_tick = time.monotonic()
        self.last_save = self.last_tick
        self.last_controls_tick = 0.0
        self.last_review_poll = 0.0
        self.overtime_key = self.state.get("overtime_key", "")
        self.laser_until = 0.0
        self.laser_y = 0.0
        self.narrator = Narrator()
        self.narrator.voice_region = self.state.get("voice_region", "en-GB")
        self.narrator.vi_voice = self.state.get("vi_voice", "Nữ")
        self.narrator.sound_on = bool(self.state.get("sound_on", True))
        self.narrator.vi_on = bool(self.state.get("vi_on", True))
        self.last_word = self.by_key.get(self.state.get("last_word"))
        self._build_ui()
        self._update_controls()
        if self.queue and self.stage_goal > self.killed:
            self.global_wave = max(0, self.global_wave - 1)
            self._start_wave()
            if self.paused:
                self._pause(force=True)
        else:
            self._start_stage()
        self.root.after(50, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Game.TCombobox", fieldbackground="#193754", background="#193754", foreground=TEXT, arrowcolor=TEXT, padding=7)
        style.map("Game.TCombobox", fieldbackground=[("readonly", "#193754")], foreground=[("readonly", TEXT)])
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True, padx=18, pady=12)
        top = tk.Frame(shell, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text="✦ WORD RUNNER", bg=BG, fg=MINT, font=("DejaVu Sans", 19, "bold")).pack(side="left", padx=(0, 18))
        self.mode_var = tk.StringVar(value=MODES[self.mode])
        mode = ttk.Combobox(top, textvariable=self.mode_var, values=list(MODES.values()), width=20, state="readonly", style="Game.TCombobox")
        mode.pack(side="left", padx=4)
        mode.bind("<<ComboboxSelected>>", self._change_mode)
        self.book_var = tk.StringVar(value=BOOKS[self.book])
        book = ttk.Combobox(top, textvariable=self.book_var, values=list(BOOKS.values()), width=18, state="readonly", style="Game.TCombobox")
        book.pack(side="left", padx=4)
        book.bind("<<ComboboxSelected>>", self._change_book)
        self.pause_button = self._button(top, "⏸ Pause", self._pause, "left")
        self.speed_button = self._button(top, "⏩ 1×", self._speed_up, "left")
        self._button(top, "↺ Reset", self._reset, "left")
        self._button(top, "🏆 Hạng", self._show_rankings, "right")

        tk.Label(shell, text="Gõ từ. Bắn quái. Qua màn.", bg=BG, fg=TEXT, font=("DejaVu Sans", 22, "bold")).pack(pady=(10, 1))
        tk.Label(shell, text="20 màn mỗi quyển · số đợt tùy tiến độ · không game over", bg=BG, fg=MUTED, font=("DejaVu Sans", 11)).pack()
        hud = tk.Frame(shell, bg=BG)
        hud.pack(fill="x", pady=(12, 5))
        self.stage_label = self._chip(hud, "Màn 1/10")
        self.kill_label = self._chip(hud, "Hạ 0/20")
        self.wave_label = self._chip(hud, "Đợt 1")
        self.total_label = self._chip(hud, "Tổng 0", "right")
        self.timer_label = self._chip(hud, "15s", "right")
        self.daily_label = self._chip(hud, "Hôm nay 30:00", "right")

        self.canvas = tk.Canvas(shell, height=335, bg="#0e2746", highlightthickness=2, highlightbackground=EDGE)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._click_enemy)
        self.message = tk.StringVar(value="Gõ để khóa mục tiêu hoặc bấm chọn quái.")
        tk.Label(shell, textvariable=self.message, anchor="w", bg="#0b2744", fg=TEXT, padx=10, pady=6, font=("DejaVu Sans", 10, "bold")).pack(fill="x", pady=(6, 8))

        below = tk.Frame(shell, bg=BG)
        below.pack(fill="x")
        input_panel = tk.Frame(below, bg=PANEL, highlightbackground=EDGE, highlightthickness=1, padx=12, pady=9)
        input_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.input_label = tk.Label(input_panel, text="GÕ TỪ TIẾNG ANH TRÊN QUÁI", bg=PANEL, fg=MUTED, font=("DejaVu Sans", 10, "bold"))
        self.input_label.pack(anchor="w")
        row = tk.Frame(input_panel, bg=PANEL)
        row.pack(fill="x", pady=(5, 1))
        self.answer_var = tk.StringVar()
        self.entry = tk.Entry(row, textvariable=self.answer_var, bg="#071c31", fg="white", insertbackground="white", relief="flat", font=("DejaVu Sans", 18, "bold"))
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<Escape>", self._escape)
        self.answer_var.trace_add("write", self._answer_changed)
        self._button(row, "Bắn ↗", self._submit, "left", coral=True)
        self.feedback = tk.StringVar()
        tk.Label(input_panel, textvariable=self.feedback, anchor="w", bg=PANEL, fg=MINT, font=("DejaVu Sans", 10, "bold")).pack(fill="x", pady=(3, 0))

        stats = tk.Frame(below, bg=PANEL, highlightbackground=EDGE, highlightthickness=1, padx=12, pady=9, width=280)
        stats.pack(side="left", fill="y")
        stats.pack_propagate(False)
        tk.Label(stats, text="TIẾN ĐỘ MÀN NÀY", bg=PANEL, fg=MUTED, font=("DejaVu Sans", 10, "bold")).pack(anchor="w")
        self.progress_label = tk.Label(stats, text="0/20", bg=PANEL, fg=TEXT, font=("DejaVu Sans", 20, "bold"))
        self.progress_label.pack(anchor="e")
        self.available_label = tk.Label(stats, text="", bg=PANEL, fg=MUTED, font=("DejaVu Sans", 9))
        self.available_label.pack(anchor="w")

        footer = tk.Frame(shell, bg=BG)
        footer.pack(fill="x", pady=(10, 0))
        self.region_var = tk.StringVar(value="Anh–Anh" if self.narrator.voice_region == "en-GB" else "Anh–Mỹ")
        region = ttk.Combobox(footer, textvariable=self.region_var, values=["Anh–Anh", "Anh–Mỹ"], width=10, state="readonly", style="Game.TCombobox")
        region.pack(side="left", padx=(0, 6))
        region.bind("<<ComboboxSelected>>", self._change_region)
        self.vi_voice_var = tk.StringVar(value="Việt · " + self.narrator.vi_voice)
        vi_voice = ttk.Combobox(footer, textvariable=self.vi_voice_var, values=["Việt · Nữ", "Việt · Nam"], width=11, state="readonly", style="Game.TCombobox")
        vi_voice.pack(side="left", padx=(0, 6))
        vi_voice.bind("<<ComboboxSelected>>", self._change_vi_voice)
        self.vi_button = self._button(footer, "🇻🇳 Việt: Bật", self._toggle_vi, "left")
        self.sound_button = self._button(footer, "🔊 Âm thanh", self._toggle_sound, "left")
        self._button(footer, "↻ Nghe lại", self._replay, "left")
        self._button(footer, "Đổi đợt ↗", self._next_wave, "right")
        self.audio_note = tk.Label(shell, text="", bg=BG, fg=MUTED, font=("DejaVu Sans", 9))
        self.audio_note.pack(anchor="w", pady=(4, 0))

    def _button(self, parent, text, command, side, coral=False):
        bg = CORAL if coral else "#193754"
        fg = BG if coral else TEXT
        button = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=MINT,
                           activeforeground=BG, relief="flat", padx=10, pady=6, font=("DejaVu Sans", 10, "bold"))
        button.pack(side=side, padx=3)
        return button

    def _chip(self, parent, text, side="left"):
        label = tk.Label(parent, text=text, bg="#0b2744", fg=TEXT, padx=10, pady=6, font=("DejaVu Sans", 10, "bold"))
        label.pack(side=side, padx=3)
        return label

    def _pool(self) -> list[dict]:
        return [w for w in self.words if self.book == "all" or str(w["book"]) == self.book]

    def _day_key(self) -> str:
        return f"{datetime.now():%Y-%m-%d}:{self.book}"

    def _daily_left(self) -> int:
        return max(0, 1800 - int(self.daily.get(self._day_key(), 0)))

    def _save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "save_version": SAVE_VERSION, "book": self.book, "mode": self.mode, "stage": self.stage, "cycle": self.cycle,
            "total": self.total, "global_wave": self.global_wave, "killed": self.killed,
            "stage_goal": self.stage_goal, "speed_index": self.speed_index,
            "queue": self.queue, "active": [e["key"] for e in self.active], "paused": self.paused,
            "learned": sorted(self.learned), "reviews": self.reviews, "rankings": self.rankings,
            "daily": self.daily, "overtime_key": self.overtime_key,
            "voice_region": self.narrator.voice_region, "vi_voice": self.narrator.vi_voice,
            "sound_on": self.narrator.sound_on, "vi_on": self.narrator.vi_on,
            "last_word": word_key(self.last_word) if self.last_word else None,
        }
        temp = STATE_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temp.replace(STATE_FILE)
        self.last_save = time.monotonic()

    def _update_controls(self):
        self.pause_button.configure(text="▶ Tiếp tục" if self.paused else "⏸ Pause")
        self.speed_button.configure(text=f"⏩ {SPEEDS[self.speed_index]:g}×")
        self.vi_button.configure(text="🇻🇳 Việt: Bật" if self.narrator.vi_on else "🇻🇳 Việt: Tắt")
        self.sound_button.configure(text="🔊 Âm thanh" if self.narrator.sound_on else "🔇 Âm thanh")
        self.entry.configure(state="disabled" if self.paused or self.transitioning else "normal")
        self.input_label.configure(text="GÕ TỪ TIẾNG ANH TRÊN QUÁI" if self.mode == "copy" else "NHỚ TỪ THEO NGHĨA VÀ PHIÊN ÂM")
        self.stage_label.configure(text=f"Màn {self.stage}/{STAGE_COUNT}")
        self.kill_label.configure(text=f"Hạ {self.killed}/{self.stage_goal}")
        self.wave_label.configure(text=f"Đợt {self.global_wave}")
        self.total_label.configure(text=f"Tổng {self.total}")
        left = self._daily_left()
        self.daily_label.configure(text="Hôm nay: Học thêm" if self.overtime_key == self._day_key() else f"Hôm nay {left//60:02d}:{left%60:02d}")
        self.progress_label.configure(text=f"{self.killed}/{self.stage_goal}")
        pool = self._pool()
        if self.mode == "review":
            due = sum(1 for w in pool if self.reviews.get(word_key(w), {}).get("due", float("inf")) <= time.time())
            self.available_label.configure(text=f"Đến lịch ôn: {due} từ")
        else:
            count = sum(word_key(w) in self.learned for w in pool)
            self.available_label.configure(text=f"Đã học {count:,}/{len(pool):,} từ")

    def _clear_pending(self):
        for name in ("pending_job", "victory_job"):
            job = getattr(self, name)
            if job:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, name, None)

    def _start_stage(self):
        self._clear_pending()
        self.active = []
        self.target = None
        self.transitioning = False
        self.paused = False
        self.book_finished = False
        pool = self._pool()
        now = time.time()
        candidates = [w for w in pool if (self.reviews.get(word_key(w), {}).get("due", float("inf")) <= now)
                      if self.mode == "review"] if self.mode == "review" else [w for w in pool if word_key(w) not in self.learned]
        random.shuffle(candidates)
        if not candidates:
            self.stage_goal = 0
            self.killed = 0
            self.queue = []
            if self.mode == "review":
                self.message.set("Chưa có từ đến lịch ôn. Hãy học ở Phần 1 hoặc 2 rồi quay lại.")
            else:
                self.book_finished = True
                self._book_complete()
            self._update_controls()
            self._save()
            return
        if self.mode == "review":
            self.stage_goal = min(15 + 5 * self.stage, len(candidates))
        else:
            self.stage_goal = math.ceil(len(candidates) / (STAGE_COUNT - self.stage + 1))
        self.killed = 0
        self.queue = [word_key(w) for w in candidates[:self.stage_goal]]
        self._update_controls()
        self._start_wave()

    def _start_wave(self):
        self.pending_job = None
        if self.paused or self.transitioning:
            return
        size = min(2 + (self.stage - 1) // 2, 6)
        incoming = self.queue[:size]
        self.queue = self.queue[size:]
        if not incoming:
            return
        self.active = [{"key": k, "word": self.by_key[k]} for k in incoming]
        self.wave_words = list(incoming)
        self.wave_hits = set()
        self.target = None
        self.global_wave += 1
        self.wave_duration = BASE_SECONDS / SPEEDS[self.speed_index]
        self.deadline = time.monotonic() + self.wave_duration
        self.answer_var.set("")
        self.message.set(f"Đợt {self.global_wave}: {len(incoming)} quái đang bay từ bên phải.")
        self._update_controls()
        self.entry.focus_set()
        self._save()

    def _tick(self):
        now = time.monotonic()
        elapsed = min(0.2, max(0, now - self.last_tick))
        self.last_tick = now
        if self.active and not self.paused and not self.transitioning:
            key = self._day_key()
            self.daily[key] = self.daily.get(key, 0) + elapsed
            if self._daily_left() == 0 and self.overtime_key != key:
                self._pause(force=True)
                if messagebox.askyesno("Đủ 30 phút hôm nay", "Tiến độ đã được lưu. Bạn muốn học thêm không?", parent=self.root):
                    self.overtime_key = key
                    self._pause(force=True, resume=True)
            if not self.paused and now >= self.deadline:
                missed = len(self.active)
                self.queue = [e["key"] for e in self.active] + self.queue
                self.active = []
                self.target = None
                self.answer_var.set("")
                self.message.set(f"Hết giờ! {missed} từ quay lại ở đợt sau.")
                self._review_wave(self._start_wave)
        if now - self.last_save > 5:
            self._save()
        if (self.mode == "review" and not self.active and not self.queue and not self.transitioning
                and self.stage_goal == 0 and now - self.last_review_poll >= 1):
            self.last_review_poll = now
            if any(self.reviews.get(word_key(w), {}).get("due", float("inf")) <= time.time() for w in self._pool()):
                self._start_stage()
        if now - self.last_controls_tick >= 1:
            self._update_controls()
            self.last_controls_tick = now
        self._draw()
        self.audio_note.configure(text=self.narrator.status)
        self.root.after(70, self._tick)

    def _draw(self):
        canvas = self.canvas
        canvas.delete("all")
        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())
        for i in range(30):
            x = (i * 191 + 31) % w
            y = (i * 97 + 39) % h
            canvas.create_oval(x, y, x + 2, y + 2, fill="#6690a9", outline="")
        canvas.create_line(0, h / 2, w, h / 2, fill="#2d6572", dash=(3, 5))
        left = self.remaining if self.paused else max(0, self.deadline - time.monotonic())
        if self.active and self.wave_duration:
            canvas.create_rectangle(0, 0, w * min(1, left / self.wave_duration), 5, fill=MINT, outline="")
        canvas.create_polygon(78, h / 2 - 22, 116, h / 2 - 20, 146, h / 2,
                              116, h / 2 + 20, 78, h / 2 + 22, 93, h / 2,
                              fill="#dcefff", outline=MINT, width=3)
        canvas.create_oval(105, h / 2 - 9, 123, h / 2 + 9, fill="#4ca2de", outline="")
        canvas.create_polygon(78, h / 2 - 8, 42, h / 2, 78, h / 2 + 8, fill=CORAL, outline="")
        if time.monotonic() < self.laser_until:
            canvas.create_line(146, h / 2, w * 0.62, self.laser_y, fill="#85f8ff", width=4)
        count = len(self.active)
        progress = 1 - min(1, left / self.wave_duration) if self.wave_duration else 0
        for i, enemy in enumerate(self.active):
            column = i // 3 if count > 3 else 0
            row = i % 3 if count > 3 else i
            y = h * ((row + 1) / (min(count, 3) + 1))
            x = w * (0.78 + column * 0.2 - progress * 0.37)
            width = min(205, w * 0.24)
            enemy["box"] = (x - width / 2, y - 27, x + width / 2, y + 36)
            word = enemy["word"]
            main = word["en"] if self.mode == "copy" else word["vi"]
            sub = (f"({word['vi']})  " if self.mode == "copy" else "") + (f"/{word['ipa']}/" if word.get("ipa") else "IPA: —")
            border = "#ffe49c" if self.target is enemy else "#7cacc5"
            canvas.create_oval(x - 16, y - 56, x + 16, y - 24, fill="#b77ee5", outline="")
            canvas.create_oval(x - 8, y - 46, x - 2, y - 40, fill=BG, outline="")
            canvas.create_oval(x + 2, y - 46, x + 8, y - 40, fill=BG, outline="")
            canvas.create_rectangle(*enemy["box"], fill="#102b48", outline=border, width=2)
            canvas.create_text(x, y - 7, text=main, width=width - 16, fill=TEXT,
                               font=("DejaVu Sans", 13 if len(main) < 20 else 11, "bold"))
            canvas.create_text(x, y + 23, text=sub, width=width - 12, fill=MUTED,
                               font=("DejaVu Sans", 9))
        self.timer_label.configure(text=f"{int(left + 0.99)}s" if self.active else "—")

    def _click_enemy(self, event):
        for enemy in self.active:
            x1, y1, x2, y2 = enemy.get("box", (0, 0, 0, 0))
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.target = enemy
                self.entry.focus_set()
                return

    def _answer_changed(self, *_):
        if self.paused or self.transitioning or not self.active:
            return
        answer = normalized(self.answer_var.get())
        if not answer:
            self.target = None
            return
        if self.target not in self.active or not normalized(self.target["word"]["en"]).startswith(answer):
            self.target = next((e for e in self.active if normalized(e["word"]["en"]).startswith(answer)), None)
        if self.target and answer == normalized(self.target["word"]["en"]):
            self._shoot(self.target)

    def _submit(self, _event=None):
        if self.paused or self.transitioning:
            return "break"
        answer = normalized(self.answer_var.get())
        enemy = next((e for e in self.active if normalized(e["word"]["en"]) == answer), None)
        if enemy:
            self._shoot(enemy)
        else:
            self.feedback.set("Chưa đúng — thử lại nhé." if answer else "Hãy gõ từ tiếng Anh.")
        return "break"

    def _escape(self, _event=None):
        self.answer_var.set("")
        self.target = None
        return "break"

    def _shoot(self, enemy):
        if enemy not in self.active:
            return
        word = enemy["word"]
        self.laser_until = time.monotonic() + 0.35
        self.laser_y = (enemy.get("box") or (0, 0, 0, self.canvas.winfo_height() / 2))[3] - 25
        self.active.remove(enemy)
        self.target = None
        self.answer_var.set("")
        self.killed += 1
        self.total += 1
        key = word_key(word)
        self.wave_hits.add(key)
        was_learned = key in self.learned
        self.learned.add(key)
        if self.mode == "review":
            level = min(int(self.reviews.get(key, {}).get("level", 0)) + 1, len(REVIEW_DELAYS) - 1)
            self.reviews[key] = {"level": level, "due": time.time() + REVIEW_DELAYS[level]}
        elif not was_learned or key not in self.reviews:
            self.reviews[key] = {"level": 0, "due": time.time() + REVIEW_DELAYS[0]}
        self.last_word = word
        self.feedback.set(f"✓ {word['en']} — {word['vi']}")
        self.narrator.speak_pair(word)
        self._update_controls()
        self._save()
        if self.mode != "review" and all(word_key(w) in self.learned for w in self._pool()):
            self._review_wave(self._book_complete)
        elif self.killed >= self.stage_goal:
            self.active = []
            self._review_wave(self._victory)
        elif not self.active:
            self._review_wave(self._start_wave)

    def _review_wave(self, next_action):
        self._clear_pending()
        self.transitioning = True
        self.active = []
        self.target = None
        self.answer_var.set("")
        self.message.set(f"Đợt {self.global_wave} đã kết thúc. Xem lại từ rồi tiếp tục.")
        self._update_controls()
        self._save()

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Ôn lại đợt {self.global_wave}")
        dialog.configure(bg=PANEL)
        dialog.geometry("560x500")
        dialog.minsize(440, 350)
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text=f"Ôn lại từ · Đợt {self.global_wave}", bg=PANEL, fg=TEXT,
                 font=("DejaVu Sans", 17, "bold")).pack(pady=(14, 5))
        tk.Label(dialog, text="Bấm 🔊 để nghe tiếng Anh rồi tiếng Việt.", bg=PANEL,
                 fg=MUTED, font=("DejaVu Sans", 10)).pack(pady=(0, 10))
        for key in self.wave_words:
            word = self.by_key[key]
            row = tk.Frame(dialog, bg="#0b2744", padx=10, pady=7)
            row.pack(fill="x", padx=16, pady=3)
            status = "✓" if key in self.wave_hits else "↻"
            tk.Label(row, text=f"{status}  {word['en']}", bg="#0b2744", fg=MINT if key in self.wave_hits else CORAL,
                     anchor="w", font=("DejaVu Sans", 12, "bold")).pack(side="left")
            self._button(row, "🔊", lambda w=word: self.narrator.speak_pair(w), "right")
            tk.Label(row, text=word["vi"], bg="#0b2744", fg=TEXT, anchor="e",
                     wraplength=220, font=("DejaVu Sans", 10)).pack(side="right", padx=8)

        def continue_game():
            dialog.grab_release()
            dialog.destroy()
            self.transitioning = False
            next_action()

        self._button(dialog, "Tiếp tục →", continue_game, "bottom", coral=True)
        dialog.protocol("WM_DELETE_WINDOW", continue_game)

    def _pause(self, force=False, resume=False):
        if self.transitioning:
            return
        if resume or (self.paused and not force):
            self.paused = False
            if self.active:
                self.deadline = time.monotonic() + self.remaining
            elif self.queue:
                self._start_wave()
            self.message.set("Tiếp tục học từ vựng.")
            self.entry.focus_set()
        elif not self.paused or force:
            self.remaining = max(0, self.deadline - time.monotonic()) if self.active else 0
            self.paused = True
            self.message.set("Đã tạm dừng. Nhấn Tiếp tục khi bạn sẵn sàng.")
            if self.pending_job:
                self.root.after_cancel(self.pending_job)
                self.pending_job = None
        self._update_controls()
        self._save()

    def _speed_up(self):
        old_duration = BASE_SECONDS / SPEEDS[self.speed_index]
        left = self.remaining if self.paused else max(0, self.deadline - time.monotonic())
        fraction = min(1, left / old_duration) if old_duration else 1
        self.speed_index = (self.speed_index + 1) % len(SPEEDS)
        self.wave_duration = BASE_SECONDS / SPEEDS[self.speed_index]
        if self.active:
            if self.paused:
                self.remaining = fraction * self.wave_duration
            else:
                self.deadline = time.monotonic() + fraction * self.wave_duration
        self._update_controls()
        self._save()

    def _next_wave(self):
        if self.paused or self.transitioning:
            return
        self.queue = [e["key"] for e in self.active] + self.queue
        self.active = []
        self._review_wave(self._start_wave)

    def _reset(self):
        if not messagebox.askyesno("Reset", "Bắt đầu lại từ màn 1? Từ đã học vẫn được ghi nhớ.", parent=self.root):
            return
        if self.total:
            self._save_ranking(False)
        self._clear_pending()
        self.stage = 1
        self.cycle = 1
        self.total = 0
        self.global_wave = 0
        self.feedback.set("")
        self._start_stage()

    def _change_mode(self, _event=None):
        new_mode = next(k for k, v in MODES.items() if v == self.mode_var.get())
        if new_mode == self.mode:
            return
        prior_review = self.mode == "review"
        self.mode = new_mode
        self.answer_var.set("")
        if prior_review or new_mode == "review":
            self.stage = 1
            self._start_stage()
        else:
            self._update_controls()
            self._save()

    def _change_book(self, _event=None):
        new_book = next(k for k, v in BOOKS.items() if v == self.book_var.get())
        if new_book == self.book:
            return
        if self.total:
            self._save_ranking(False)
        self.book = new_book
        self.stage = 1
        self.total = 0
        self.global_wave = 0
        self.feedback.set("")
        self._start_stage()

    def _change_region(self, _event=None):
        self.narrator.voice_region = "en-GB" if self.region_var.get() == "Anh–Anh" else "en-US"
        self._save()

    def _change_vi_voice(self, _event=None):
        self.narrator.vi_voice = "Nam" if self.vi_voice_var.get().endswith("Nam") else "Nữ"
        self._save()

    def _toggle_vi(self):
        self.narrator.vi_on = not self.narrator.vi_on
        if not self.narrator.vi_on:
            self.narrator.stop()
        self._update_controls()
        self._save()

    def _toggle_sound(self):
        self.narrator.sound_on = not self.narrator.sound_on
        if not self.narrator.sound_on:
            self.narrator.stop()
        self._update_controls()
        self._save()

    def _replay(self):
        if self.last_word:
            self.narrator.speak_pair(self.last_word)

    def _save_ranking(self, completed: bool):
        self.rankings.append({"book": BOOKS[self.book], "stage": self.stage, "words": self.total,
                              "wave": self.global_wave, "completed": completed, "date": datetime.now().strftime("%d/%m/%Y")})
        self.rankings.sort(key=lambda r: (r["words"], r["stage"]), reverse=True)
        self.rankings = self.rankings[:10]

    def _show_rankings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Bảng xếp hạng")
        dialog.configure(bg=PANEL)
        dialog.geometry("500x400")
        tk.Label(dialog, text="🏆 Bảng xếp hạng", bg=PANEL, fg=MINT, font=("DejaVu Sans", 18, "bold")).pack(pady=16)
        if not self.rankings:
            tk.Label(dialog, text="Chưa có phiên đã lưu.", bg=PANEL, fg=TEXT).pack()
        for i, rank in enumerate(self.rankings, 1):
            tk.Label(dialog, text=f"#{i}  {rank['book']} · màn {rank['stage']} · {rank['words']} từ · {rank['date']}",
                     bg=PANEL, fg=TEXT, anchor="w", font=("DejaVu Sans", 10)).pack(fill="x", padx=20, pady=4)
        self._button(dialog, "Đóng", dialog.destroy, "left")

    def _victory(self):
        self._update_controls()
        self._save()
        self.message.set(f"🏆 Hoàn thành màn {self.stage}!")
        dialog = tk.Toplevel(self.root)
        dialog.title("Chiến thắng")
        dialog.configure(bg=PANEL)
        dialog.geometry("420x250")
        dialog.transient(self.root)
        tk.Label(dialog, text="🏆", bg=PANEL, fg=MINT, font=("DejaVu Sans", 52)).pack(pady=(10, 0))
        tk.Label(dialog, text=f"Hoàn thành màn {self.stage}!", bg=PANEL, fg=TEXT, font=("DejaVu Sans", 18, "bold")).pack()
        tk.Label(dialog, text=f"Đã hạ {self.killed} quái · tổng {self.total} từ", bg=PANEL, fg=MUTED).pack(pady=7)

        def advance():
            if dialog.winfo_exists():
                dialog.destroy()
            if self.victory_job:
                self.root.after_cancel(self.victory_job)
            self.victory_job = None
            if self.stage == STAGE_COUNT:
                self.stage = 1
                self.cycle += 1
                self.total = 0
                self.global_wave = 0
            else:
                self.stage += 1
            self._start_stage()

        self._button(dialog, "Màn tiếp theo →", advance, "left", coral=True)
        dialog.protocol("WM_DELETE_WINDOW", advance)
        self.victory_job = self.root.after(5000, advance)

    def _book_complete(self):
        self.book_finished = True
        self.transitioning = True
        self._save_ranking(True)
        self.message.set(f"🏆 Hoàn thành {BOOKS[self.book]}!")
        self._update_controls()
        messagebox.showinfo("Hoàn thành quyển", "Bạn đã học hết các từ trong lựa chọn này. Chuyển sang Phần 3 để ôn theo lịch.", parent=self.root)
        self._save()

    def _close(self):
        self.narrator.stop()
        self._save()
        self.root.destroy()


def main():
    root = tk.Tk()
    WordRunner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
