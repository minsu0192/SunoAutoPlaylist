"""
설정 창 (tkinter) — 탭형 리뉴얼
suno_menu_bar.py에서 subprocess로 실행됨 (rumps threading 충돌 방지).

저장 위치: ~/.suno_config.json
"""

import json
import os
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

CONFIG_FILE = Path.home() / ".suno_config.json"

DAYS_KR = [("mon", "월"), ("tue", "화"), ("wed", "수"),
           ("thu", "목"), ("fri", "금"), ("sat", "토"), ("sun", "일")]

STYLE_PRESETS = [
    ("직접 입력", ""),
    ("Lo-fi 힙합",          "lofi, hip hop, chill, relaxing"),
    ("시네마틱 오케스트라",  "cinematic, orchestral, emotional, epic"),
    ("팝 발라드",            "pop, ballad, emotional, piano"),
    ("EDM / 일렉트로닉",    "edm, electronic, upbeat, energetic"),
    ("재즈 / 스윙",         "jazz, swing, piano, brass"),
    ("어쿠스틱 포크",        "acoustic, folk, guitar, warm"),
    ("K-Pop",               "kpop, synth, catchy, modern"),
]

DEFAULTS = {
    "anthropic_api_key":        "",
    "projects_root":            str(Path.home() / "SunoProjects"),
    "default_style":            "cinematic, orchestral, emotional",
    "vocal_type":               "female",
    "default_select":           "longest",
    "songs_count":              2,
    # 예약
    "schedule_enabled":         False,
    "schedule_time":            "02:00",
    "schedule_days":            ["mon","tue","wed","thu","fri","sat","sun"],
    # YouTube
    "youtube_auto_upload":      False,
    "youtube_client_secrets":   "",
    "youtube_playlist_id":      "",
    "youtube_privacy":          "public",
    "youtube_channel_url":      "",
    "youtube_channel_style":    {},
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


# ─────────────────────────────────────────────────────────────────────────────

class SettingsWindow:

    def __init__(self):
        self.cfg = load_config()

        self.root = tk.Tk()
        self.root.title("수노 자동화 설정")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)

        W, H = 640, 580
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.root.minsize(580, 500)

        self._patch_paste()
        self._build_ui()

    # ── 붙여넣기 패치 ─────────────────────────────────────

    def _patch_paste(self):
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
            self.root.bind_class(cls, "<Command-a>",
                                 lambda e: e.widget.select_range(0, "end"))

    # ── UI 빌드 ──────────────────────────────────────────

    def _build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self._build_tab_basic(nb)
        self._build_tab_youtube(nb)
        self._build_tab_advanced(nb)

        bf = ttk.Frame(self.root)
        bf.pack(fill="x", padx=12, pady=10)
        ttk.Button(bf, text="취소", width=10,
                   command=self.root.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bf, text="저장", width=10,
                   command=self._save).pack(side="right")

    # ── 탭 1: 기본 설정 ──────────────────────────────────

    def _build_tab_basic(self, nb):
        tab = ttk.Frame(nb, padding=16)
        nb.add(tab, text="  기본 설정  ")
        row = 0

        # API 키
        self._lbl(tab, "Anthropic API 키", row); row += 1
        self.var_api = tk.StringVar(value=self.cfg["anthropic_api_key"])
        f = ttk.Frame(tab)
        f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 10)); row += 1
        ttk.Entry(f, textvariable=self.var_api, show="*",
                  font=("Menlo", 12)).pack(side="left", fill="x", expand=True)
        ttk.Button(f, text="붙여넣기", command=self._paste_api).pack(side="left", padx=(6,0))

        # 입력 폴더
        self._lbl(tab, "프로젝트 폴더 (이미지를 input/ 안에 넣으세요)", row); row += 1
        self.var_root = tk.StringVar(value=self.cfg["projects_root"])
        f = ttk.Frame(tab)
        f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 10)); row += 1
        ttk.Entry(f, textvariable=self.var_root,
                  font=("Helvetica", 12)).pack(side="left", fill="x", expand=True)
        ttk.Button(f, text="찾기", command=self._browse_folder).pack(side="left", padx=(6,0))

        # 스타일 프리셋
        self._lbl(tab, "음악 스타일", row); row += 1
        preset_f = ttk.Frame(tab)
        preset_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 2)); row += 1
        self.var_preset = tk.StringVar(value="직접 입력")
        cb = ttk.Combobox(preset_f, textvariable=self.var_preset,
                          values=[p[0] for p in STYLE_PRESETS],
                          state="readonly", width=20)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self._on_preset)
        ttk.Label(preset_f, text="← 프리셋 선택 또는 직접 입력",
                  foreground="#888", font=("Helvetica", 10)).pack(side="left", padx=8)

        self.var_style = tk.StringVar(value=self.cfg["default_style"])
        ttk.Entry(tab, textvariable=self.var_style,
                  font=("Helvetica", 12)).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)); row += 1

        # 보컬
        self._lbl(tab, "보컬 타입", row); row += 1
        self.var_vocal = tk.StringVar(value=self.cfg["vocal_type"])
        vf = ttk.Frame(tab)
        vf.grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 10)); row += 1
        for val, lbl in [("female", "여성"), ("male", "남성"), ("none", "없음")]:
            ttk.Radiobutton(vf, text=lbl, variable=self.var_vocal, value=val).pack(side="left", padx=10)

        # 곡 수 + 선택 방식
        cf = ttk.Frame(tab)
        cf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6)); row += 1

        cnt_f = ttk.LabelFrame(cf, text="한 번에 생성할 곡 수", padding=8)
        cnt_f.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.var_count = tk.IntVar(value=self.cfg["songs_count"])
        spin = ttk.Spinbox(cnt_f, from_=1, to=20, textvariable=self.var_count,
                           width=5, font=("Helvetica", 13))
        spin.pack(side="left")
        ttk.Label(cnt_f, text="곡  (최대 20)",
                  font=("Helvetica", 11)).pack(side="left", padx=6)

        sel_f = ttk.LabelFrame(cf, text="곡 선택 방식", padding=8)
        sel_f.pack(side="left", fill="both", expand=True)
        self.var_select = tk.StringVar(value=self.cfg["default_select"])
        for val, lbl in [("longest", "가장 긴 곡"), ("random", "랜덤"), ("manual", "수동")]:
            ttk.Radiobutton(sel_f, text=lbl, variable=self.var_select,
                            value=val).pack(side="left", padx=6)

        tab.columnconfigure(0, weight=1)

    # ── 탭 2: YouTube ─────────────────────────────────────

    def _build_tab_youtube(self, nb):
        tab = ttk.Frame(nb, padding=16)
        nb.add(tab, text="  YouTube  ")
        row = 0

        # 자동 업로드
        self.var_yt_upload = tk.BooleanVar(value=self.cfg["youtube_auto_upload"])
        ttk.Checkbutton(tab, text="완료 후 자동으로 YouTube에 업로드",
                        variable=self.var_yt_upload,
                        command=self._toggle_yt).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 12)); row += 1

        # OAuth 파일
        self._lbl(tab, "Google OAuth 인증 파일 (client_secrets.json)", row); row += 1
        f = ttk.Frame(tab)
        f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 6)); row += 1
        self.var_secrets = tk.StringVar(value=self.cfg["youtube_client_secrets"])
        ttk.Entry(f, textvariable=self.var_secrets,
                  font=("Helvetica", 11)).pack(side="left", fill="x", expand=True)
        ttk.Button(f, text="찾기", command=self._browse_secrets).pack(side="left", padx=(6,0))

        self._yt_auth_btn = ttk.Button(tab,
            text="🔑 YouTube 계정 인증 (브라우저 열림)",
            command=self._run_yt_auth)
        self._yt_auth_btn.grid(row=row, column=0, columnspan=2,
                                sticky="w", pady=(0, 12)); row += 1

        ttk.Separator(tab).grid(row=row, column=0, columnspan=2,
                                sticky="ew", pady=8); row += 1

        # 채널 스타일 분석
        self._lbl(tab, "업로드 스타일 참고 채널 URL (1회 분석 후 저장)", row); row += 1
        f = ttk.Frame(tab)
        f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 4)); row += 1
        self.var_channel_url = tk.StringVar(value=self.cfg["youtube_channel_url"])
        ttk.Entry(f, textvariable=self.var_channel_url,
                  font=("Helvetica", 11),
                  placeholder_text="https://www.youtube.com/@channelname").pack(
            side="left", fill="x", expand=True)
        self._analyze_btn = ttk.Button(f, text="🔍 채널 분석",
                                       command=self._analyze_channel)
        self._analyze_btn.pack(side="left", padx=(6,0))

        # 분석 상태 표시
        style_info = self.cfg.get("youtube_channel_style", {})
        status_text = f"✅ 분석됨: {style_info.get('style_notes', '')[:40]}" if style_info else "미분석"
        self._channel_status = ttk.Label(tab, text=status_text,
                                          foreground="#4a4", font=("Helvetica", 10))
        self._channel_status.grid(row=row, column=0, columnspan=2,
                                   sticky="w", pady=(0, 10)); row += 1

        ttk.Separator(tab).grid(row=row, column=0, columnspan=2,
                                sticky="ew", pady=8); row += 1

        # 플레이리스트 + 공개 범위
        self._lbl(tab, "플레이리스트 ID (선택)", row); row += 1
        self.var_playlist = tk.StringVar(value=self.cfg["youtube_playlist_id"])
        ttk.Entry(tab, textvariable=self.var_playlist,
                  font=("Helvetica", 12)).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(2, 10)); row += 1

        self._lbl(tab, "공개 범위", row); row += 1
        self.var_privacy = tk.StringVar(value=self.cfg["youtube_privacy"])
        pf = ttk.Frame(tab)
        pf.grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 10)); row += 1
        for val, lbl in [("public", "공개"), ("unlisted", "미등재"), ("private", "비공개")]:
            ttk.Radiobutton(pf, text=lbl, variable=self.var_privacy,
                            value=val).pack(side="left", padx=10)

        self._toggle_yt()
        tab.columnconfigure(0, weight=1)

    # ── 탭 3: 고급 설정 ──────────────────────────────────

    def _build_tab_advanced(self, nb):
        tab = ttk.Frame(nb, padding=16)
        nb.add(tab, text="  고급 설정  ")
        row = 0

        # 예약 실행
        self._lbl(tab, "예약 자동 실행", row); row += 1

        sched_f = ttk.LabelFrame(tab, text="예약 설정", padding=10)
        sched_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 12)); row += 1

        # 활성화 토글
        self.var_sched_on = tk.BooleanVar(value=self.cfg["schedule_enabled"])
        ttk.Checkbutton(sched_f, text="예약 실행 활성화",
                        variable=self.var_sched_on,
                        command=self._toggle_schedule).grid(
            row=0, column=0, columnspan=7, sticky="w", pady=(0, 8))

        # 시간 (HH:MM 드롭다운)
        time_f = ttk.Frame(sched_f)
        time_f.grid(row=1, column=0, columnspan=7, sticky="w", pady=(0, 8))
        ttk.Label(time_f, text="실행 시간:  ", font=("Helvetica", 12)).pack(side="left")

        hh, mm = "02", "00"
        if self.cfg["schedule_time"]:
            parts = self.cfg["schedule_time"].split(":")
            if len(parts) == 2:
                hh, mm = parts[0].zfill(2), parts[1].zfill(2)

        self.var_hour   = tk.StringVar(value=hh)
        self.var_minute = tk.StringVar(value=mm)
        hours   = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        self._hour_cb = ttk.Combobox(time_f, textvariable=self.var_hour,
                                      values=hours, width=4, state="readonly")
        self._hour_cb.pack(side="left")
        ttk.Label(time_f, text=" : ", font=("Helvetica", 13)).pack(side="left")
        self._min_cb = ttk.Combobox(time_f, textvariable=self.var_minute,
                                     values=minutes, width=4, state="readonly")
        self._min_cb.pack(side="left")

        # 요일 체크박스
        day_f = ttk.Frame(sched_f)
        day_f.grid(row=2, column=0, columnspan=7, sticky="w")
        ttk.Label(day_f, text="반복 요일:  ", font=("Helvetica", 12)).pack(side="left")
        saved_days = self.cfg.get("schedule_days", [d for d, _ in DAYS_KR])
        self._day_vars = {}
        for key, label in DAYS_KR:
            v = tk.BooleanVar(value=(key in saved_days))
            self._day_vars[key] = v
            self._day_cbs = getattr(self, "_day_cbs", [])
            cb = ttk.Checkbutton(day_f, text=label, variable=v)
            cb.pack(side="left", padx=3)
            self._day_cbs.append(cb)

        self._toggle_schedule()

        ttk.Separator(tab).grid(row=row, column=0, columnspan=2,
                                sticky="ew", pady=8); row += 1

        # UI 재학습
        self._lbl(tab, "Suno UI 좌표 학습", row); row += 1
        ttk.Label(tab,
                  text="Suno 화면이 바뀌었거나 처음 설정할 때 실행하세요.",
                  foreground="#666", font=("Helvetica", 11)).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 6)); row += 1

        btn_f = ttk.Frame(tab)
        btn_f.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 12)); row += 1
        ttk.Button(btn_f, text="🎬 녹화 학습 (자연스럽게 진행)",
                   command=self._run_learn_record).pack(side="left", padx=(0, 8))
        ttk.Button(btn_f, text="🖱 수동 학습 (요소별 클릭)",
                   command=self._run_learn_manual).pack(side="left")

        ttk.Separator(tab).grid(row=row, column=0, columnspan=2,
                                sticky="ew", pady=8); row += 1

        # 로그
        self._lbl(tab, "로그", row); row += 1
        ttk.Button(tab, text="📋 로그 파일 열기",
                   command=self._open_log).grid(
            row=row, column=0, sticky="w", pady=(2, 0)); row += 1

        tab.columnconfigure(0, weight=1)

    # ── 헬퍼 ──────────────────────────────────────────────

    def _lbl(self, parent, text, row):
        ttk.Label(parent, text=text,
                  font=("Helvetica", 12, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))

    # ── 콜백 ──────────────────────────────────────────────

    def _paste_api(self):
        try:
            self.var_api.set(self.root.clipboard_get().strip())
        except Exception:
            messagebox.showerror("오류", "클립보드가 비어 있거나 접근할 수 없습니다.")

    def _browse_folder(self):
        d = filedialog.askdirectory(title="프로젝트 폴더 선택",
                                    initialdir=self.var_root.get())
        if d:
            self.var_root.set(d)

    def _browse_secrets(self):
        f = filedialog.askopenfilename(
            title="client_secrets.json 선택",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
        )
        if f:
            self.var_secrets.set(f)

    def _on_preset(self, _=None):
        sel = self.var_preset.get()
        for name, style in STYLE_PRESETS:
            if name == sel and style:
                self.var_style.set(style)
                break

    def _toggle_yt(self):
        state = "normal" if self.var_yt_upload.get() else "disabled"
        self._yt_auth_btn.configure(state=state)

    def _toggle_schedule(self):
        on = self.var_sched_on.get()
        state = "normal" if on else "disabled"
        self._hour_cb.configure(state="readonly" if on else "disabled")
        self._min_cb.configure(state="readonly" if on else "disabled")
        for cb in getattr(self, "_day_cbs", []):
            cb.configure(state=state)

    def _run_yt_auth(self):
        secrets = self.var_secrets.get().strip()
        if not secrets or not Path(secrets).exists():
            messagebox.showerror("오류", "먼저 client_secrets.json 파일을 선택하세요.")
            return
        self._save(quiet=True)
        subprocess.Popen([sys.executable,
                          str(Path(__file__).parent / "youtube_upload.py"),
                          "--auth-only", "--secrets", secrets])
        messagebox.showinfo("YouTube 인증",
                            "브라우저가 열립니다.\n구글 계정으로 로그인하고 허용을 클릭하세요.")

    def _analyze_channel(self):
        url = self.var_channel_url.get().strip()
        if not url:
            messagebox.showerror("오류", "YouTube 채널 URL을 입력하세요.")
            return
        api_key = self.var_api.get().strip() or self.cfg.get("anthropic_api_key", "")
        if not api_key:
            messagebox.showerror("오류", "Anthropic API 키를 먼저 입력하세요.")
            return
        self._save(quiet=True)
        self._analyze_btn.configure(state="disabled", text="분석 중...")
        self.root.update()
        try:
            from suno_channel_analyzer import analyze_channel_style
            style = analyze_channel_style(url, api_key)
            cfg = load_config()
            cfg["youtube_channel_url"]   = url
            cfg["youtube_channel_style"] = style
            save_config(cfg)
            self.cfg = cfg
            notes = style.get("style_notes", "")[:50]
            self._channel_status.configure(text=f"✅ 분석 완료: {notes}", foreground="#4a4")
            messagebox.showinfo("분석 완료",
                                f"채널 스타일 분석 완료!\n\n{style.get('style_notes','')}")
        except Exception as e:
            messagebox.showerror("분석 실패", str(e))
        finally:
            self._analyze_btn.configure(state="normal", text="🔍 채널 분석")

    def _run_learn_record(self):
        self._save(quiet=True)
        subprocess.Popen([sys.executable,
                          str(Path(__file__).parent / "suno_learn.py"), "--record"])
        messagebox.showinfo("녹화 학습",
                            "터미널에서 안내에 따라 진행하세요.\n\n"
                            "① suno.com/create → Advanced 탭 열기\n"
                            "② 숫자 키로 각 요소 마킹 (안내 참고)\n"
                            "③ 0 키로 종료")

    def _run_learn_manual(self):
        self._save(quiet=True)
        subprocess.Popen([sys.executable,
                          str(Path(__file__).parent / "suno_learn.py"), "--manual"])
        messagebox.showinfo("수동 학습",
                            "터미널에서 각 요소 위에 마우스를 올리고\nEnter를 누르세요.")

    def _open_log(self):
        log = Path.home() / ".suno_auto.log"
        if log.exists():
            subprocess.Popen(["open", str(log)])
        else:
            messagebox.showinfo("로그", "아직 로그가 없습니다.")

    # ── 저장 ──────────────────────────────────────────────

    def _save(self, quiet: bool = False):
        # 예약 시간 조합
        schedule_time = ""
        if self.var_sched_on.get():
            schedule_time = f"{self.var_hour.get()}:{self.var_minute.get()}"

        schedule_days = [k for k, v in self._day_vars.items() if v.get()]

        cfg = {
            **self.cfg,
            "anthropic_api_key":      self.var_api.get().strip(),
            "projects_root":          self.var_root.get().strip(),
            "default_style":          self.var_style.get().strip(),
            "vocal_type":             self.var_vocal.get(),
            "default_select":         self.var_select.get(),
            "songs_count":            int(self.var_count.get()),
            "schedule_enabled":       self.var_sched_on.get(),
            "schedule_time":          schedule_time,
            "schedule_days":          schedule_days,
            "youtube_auto_upload":    self.var_yt_upload.get(),
            "youtube_client_secrets": self.var_secrets.get().strip(),
            "youtube_playlist_id":    self.var_playlist.get().strip(),
            "youtube_privacy":        self.var_privacy.get(),
            "youtube_channel_url":    self.var_channel_url.get().strip(),
        }
        save_config(cfg)
        if not quiet:
            messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SettingsWindow().run()
