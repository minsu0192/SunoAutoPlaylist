"""
설정 창 (tkinter)
suno_menu_bar.py에서 subprocess로 실행됨 (rumps threading 충돌 방지).

저장 위치: ~/.suno_config.json
"""

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

CONFIG_FILE = Path.home() / ".suno_config.json"

DEFAULTS = {
    "anthropic_api_key":   "",
    "projects_root":       str(Path.home() / "SunoProjects"),
    "default_style":       "cinematic, orchestral, emotional",
    "vocal_type":          "female",
    "default_select":      "longest",
    "schedule_time":       "",
    "youtube_playlist_id": "",
    "youtube_privacy":     "public",
    "youtube_auto_upload": False,
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_config(cfg: dict):
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class SettingsWindow:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.title("수노 자동화 설정")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # macOS 창 중앙 배치
        self.root.update_idletasks()
        w, h = 480, 520
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # macOS Cmd+V: 클립보드 직접 읽어서 삽입 (show="*" 필드 호환)
        def _paste(e):
            try:
                text = e.widget.clipboard_get()
                try:
                    e.widget.delete("sel.first", "sel.last")
                except Exception:
                    pass
                e.widget.insert("insert", text)
            except Exception:
                pass
            return "break"

        for cls in ("Entry", "TEntry"):
            self.root.bind_class(cls, "<Command-v>", _paste)
            self.root.bind_class(cls, "<Command-a>", lambda e: e.widget.select_range(0, "end"))

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 4}
        lpad = {"padx": 12, "pady": (8, 0)}

        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)

        row = 0

        # --- Anthropic API 키 ---
        ttk.Label(frame, text="Anthropic API 키", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **lpad); row += 1
        self.var_api_key = tk.StringVar(value=self.cfg["anthropic_api_key"])
        e = ttk.Entry(frame, textvariable=self.var_api_key, width=46, show="*")
        e.grid(row=row, column=0, columnspan=2, sticky="ew", **pad); row += 1

        # --- 프로젝트 폴더 ---
        ttk.Label(frame, text="프로젝트 폴더", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **lpad); row += 1
        self.var_root = tk.StringVar(value=self.cfg["projects_root"])
        ef = ttk.Frame(frame)
        ef.grid(row=row, column=0, columnspan=2, sticky="ew", **pad); row += 1
        ttk.Entry(ef, textvariable=self.var_root, width=36).pack(side="left", fill="x", expand=True)
        ttk.Button(ef, text="찾기", command=self._browse_folder).pack(side="left", padx=(4, 0))

        # --- 기본 스타일 ---
        ttk.Label(frame, text="기본 음악 스타일", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **lpad); row += 1
        self.var_style = tk.StringVar(value=self.cfg["default_style"])
        ttk.Entry(frame, textvariable=self.var_style, width=46).grid(
            row=row, column=0, columnspan=2, sticky="ew", **pad); row += 1

        # --- 보컬 타입 ---
        ttk.Label(frame, text="보컬 타입", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **lpad); row += 1
        self.var_vocal = tk.StringVar(value=self.cfg["vocal_type"])
        vf = ttk.Frame(frame)
        vf.grid(row=row, column=0, columnspan=2, sticky="w", **pad); row += 1
        for val, lbl in [("female", "여성"), ("male", "남성"), ("none", "없음")]:
            ttk.Radiobutton(vf, text=lbl, variable=self.var_vocal, value=val).pack(side="left", padx=6)

        # --- 선택 방식 ---
        ttk.Label(frame, text="곡 선택 방식", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **lpad); row += 1
        self.var_select = tk.StringVar(value=self.cfg["default_select"])
        sf = ttk.Frame(frame)
        sf.grid(row=row, column=0, columnspan=2, sticky="w", **pad); row += 1
        for val, lbl in [("longest", "긴 곡 자동"), ("random", "랜덤"), ("manual", "수동")]:
            ttk.Radiobutton(sf, text=lbl, variable=self.var_select, value=val).pack(side="left", padx=6)

        # --- 예약 실행 시간 ---
        ttk.Label(frame, text="예약 실행 시간 (HH:MM, 비우면 예약 없음)", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **lpad); row += 1
        self.var_schedule = tk.StringVar(value=self.cfg["schedule_time"])
        ttk.Entry(frame, textvariable=self.var_schedule, width=10).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad); row += 1

        # --- YouTube ---
        ttk.Label(frame, text="YouTube 설정", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **lpad); row += 1

        self.var_yt_upload = tk.BooleanVar(value=self.cfg["youtube_auto_upload"])
        ttk.Checkbutton(frame, text="자동 업로드", variable=self.var_yt_upload).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad); row += 1

        ttk.Label(frame, text="플레이리스트 ID").grid(row=row, column=0, sticky="w", padx=12)
        self.var_playlist = tk.StringVar(value=self.cfg["youtube_playlist_id"])
        ttk.Entry(frame, textvariable=self.var_playlist, width=32).grid(
            row=row, column=1, sticky="w", pady=4); row += 1

        ttk.Label(frame, text="공개 범위").grid(row=row, column=0, sticky="w", padx=12)
        self.var_privacy = tk.StringVar(value=self.cfg["youtube_privacy"])
        ttk.OptionMenu(frame, self.var_privacy, self.cfg["youtube_privacy"],
                       "public", "unlisted", "private").grid(
            row=row, column=1, sticky="w", pady=4); row += 1

        # --- 버튼 ---
        ttk.Separator(frame).grid(row=row, column=0, columnspan=2,
                                  sticky="ew", padx=12, pady=8); row += 1
        bf = ttk.Frame(frame)
        bf.grid(row=row, column=0, columnspan=2, sticky="e", padx=12, pady=4)
        ttk.Button(bf, text="취소", command=self.root.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bf, text="저장", command=self._save).pack(side="right")

        frame.columnconfigure(1, weight=1)

    def _browse_folder(self):
        d = filedialog.askdirectory(title="프로젝트 폴더 선택",
                                    initialdir=self.var_root.get())
        if d:
            self.var_root.set(d)

    def _save(self):
        schedule = self.var_schedule.get().strip()
        if schedule:
            import re
            if not re.match(r"^\d{1,2}:\d{2}$", schedule):
                messagebox.showerror("오류", "예약 시간 형식이 잘못됐습니다.\n예시: 02:00 또는 14:30")
                return

        new_cfg = {
            "anthropic_api_key":   self.var_api_key.get().strip(),
            "projects_root":       self.var_root.get().strip(),
            "default_style":       self.var_style.get().strip(),
            "vocal_type":          self.var_vocal.get(),
            "default_select":      self.var_select.get(),
            "schedule_time":       schedule,
            "youtube_playlist_id": self.var_playlist.get().strip(),
            "youtube_privacy":     self.var_privacy.get(),
            "youtube_auto_upload": self.var_yt_upload.get(),
        }
        save_config(new_cfg)
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SettingsWindow().run()
