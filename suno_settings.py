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

# ── 공통 폰트 상수 ──────────────────────────────────
F_TITLE  = ("Apple SD Gothic Neo", 13, "bold")   # 섹션 제목
F_LABEL  = ("Apple SD Gothic Neo", 12)            # 일반 레이블
F_SMALL  = ("Apple SD Gothic Neo", 10)            # 힌트/설명
F_ENTRY  = ("Menlo", 12)                          # 입력 필드
F_MONO   = ("Menlo", 11)                          # 모노스페이스
# 폰트 폴백 (윈도우/리눅스 호환)
import platform
if platform.system() != "Darwin":
    F_TITLE = ("Segoe UI", 13, "bold")
    F_LABEL = ("Segoe UI", 12)
    F_SMALL = ("Segoe UI", 10)
    F_ENTRY = ("Consolas", 12)
    F_MONO  = ("Consolas", 11)


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


# ── 스크롤 가능 프레임 헬퍼 ────────────────────────────
class ScrollableFrame(ttk.Frame):
    """마우스 휠 + 스크롤바가 있는 스크롤 가능한 프레임."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(self, orient="vertical",
                                         command=self._canvas.yview)
        self.inner = ttk.Frame(self._canvas)

        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._win_id = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.inner.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # 마우스 휠 바인딩 (macOS + Windows/Linux)
        self._canvas.bind("<MouseWheel>",     self._on_mousewheel)
        self._canvas.bind("<Button-4>",       self._on_mousewheel)
        self._canvas.bind("<Button-5>",       self._on_mousewheel)
        self.inner.bind("<MouseWheel>",       self._on_mousewheel)

    def _on_frame_configure(self, _=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            # macOS: event.delta는 보통 ±120
            delta = -1 if event.delta > 0 else 1
            self._canvas.yview_scroll(delta, "units")


# ─────────────────────────────────────────────────────────────────────────────

class SettingsWindow:

    def __init__(self):
        self.cfg = load_config()

        self.root = tk.Tk()
        self.root.title("수노 자동화 설정")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)

        W, H = 660, 640
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.root.minsize(600, 540)

        # ttk 스타일
        style = ttk.Style(self.root)
        style.configure("TNotebook.Tab", font=F_LABEL, padding=[10, 4])
        style.configure("Section.TLabel", font=F_TITLE)
        style.configure("Hint.TLabel", font=F_SMALL, foreground="#888888")
        style.configure("TLabelframe.Label", font=F_LABEL)

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

        def _select_all(e):
            try:
                e.widget.select_range(0, "end")
                e.widget.icursor("end")
            except Exception:
                pass
            return "break"

        for cls in ("Entry", "TEntry"):
            self.root.bind_class(cls, "<Command-v>", _paste)
            self.root.bind_class(cls, "<Control-v>", _paste)
            self.root.bind_class(cls, "<Command-a>", _select_all)
            self.root.bind_class(cls, "<Control-a>", _select_all)

    # ── UI 빌드 ──────────────────────────────────────────

    def _build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self._build_tab_basic(nb)
        self._build_tab_youtube(nb)
        self._build_tab_advanced(nb)
        self._build_tab_help(nb)

        bf = ttk.Frame(self.root)
        bf.pack(fill="x", padx=12, pady=10)
        ttk.Button(bf, text="취소", width=10,
                   command=self.root.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bf, text="저장", width=12,
                   command=self._save).pack(side="right")

    # ── 탭 1: 기본 설정 ──────────────────────────────────

    def _build_tab_basic(self, nb):
        sf = ScrollableFrame(nb)
        nb.add(sf, text="  기본 설정  ")
        tab = sf.inner
        tab.columnconfigure(0, weight=1)
        row = 0

        # ── API 키 ──────────────────────────────────────
        self._lbl(tab, "🔑  Anthropic API 키", row); row += 1
        ttk.Label(tab, text="Claude AI 기능(가사 생성, UI 감지)에 필요합니다. sk-ant-... 형식",
                  style="Hint.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)); row += 1

        self.var_api = tk.StringVar(value=self.cfg["anthropic_api_key"])
        api_f = ttk.Frame(tab)
        api_f.grid(row=row, column=0, sticky="ew", pady=(0, 14)); row += 1
        api_f.columnconfigure(0, weight=1)
        self._api_entry = ttk.Entry(api_f, textvariable=self.var_api, show="*", font=F_ENTRY)
        self._api_entry.grid(row=0, column=0, sticky="ew")
        btn_f = ttk.Frame(api_f)
        btn_f.grid(row=0, column=1, padx=(6, 0))
        ttk.Button(btn_f, text="붙여넣기", width=9,
                   command=self._paste_api).pack(side="left", padx=(0, 4))
        ttk.Button(btn_f, text="👁 표시", width=8,
                   command=self._toggle_api_show).pack(side="left")

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── 프로젝트 폴더 ────────────────────────────────
        self._lbl(tab, "📂  프로젝트 폴더", row); row += 1
        ttk.Label(tab, text="이미지 파일을 input/ 폴더 안에 넣으면 자동으로 처리됩니다.",
                  style="Hint.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)); row += 1

        self.var_root = tk.StringVar(value=self.cfg["projects_root"])
        root_f = ttk.Frame(tab)
        root_f.grid(row=row, column=0, sticky="ew", pady=(0, 14)); row += 1
        root_f.columnconfigure(0, weight=1)
        ttk.Entry(root_f, textvariable=self.var_root, font=F_ENTRY).grid(
            row=0, column=0, sticky="ew")
        ttk.Button(root_f, text="찾기", width=7,
                   command=self._browse_folder).grid(row=0, column=1, padx=(6, 0))

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── 음악 스타일 ──────────────────────────────────
        self._lbl(tab, "🎵  음악 스타일", row); row += 1
        ttk.Label(tab, text="Suno에 전달할 스타일 키워드 (영어 권장)",
                  style="Hint.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)); row += 1

        preset_f = ttk.Frame(tab)
        preset_f.grid(row=row, column=0, sticky="ew", pady=(0, 4)); row += 1
        ttk.Label(preset_f, text="프리셋:", font=F_LABEL).pack(side="left")
        self.var_preset = tk.StringVar(value="직접 입력")
        cb = ttk.Combobox(preset_f, textvariable=self.var_preset,
                          values=[p[0] for p in STYLE_PRESETS],
                          state="readonly", width=22, font=F_LABEL)
        cb.pack(side="left", padx=(6, 0))
        cb.bind("<<ComboboxSelected>>", self._on_preset)

        self.var_style = tk.StringVar(value=self.cfg["default_style"])
        ttk.Entry(tab, textvariable=self.var_style, font=F_ENTRY).grid(
            row=row, column=0, sticky="ew", pady=(0, 14)); row += 1

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── 보컬 + 생성 설정 ─────────────────────────────
        self._lbl(tab, "🎤  보컬 & 생성 설정", row); row += 1

        opt_f = ttk.Frame(tab)
        opt_f.grid(row=row, column=0, sticky="ew", pady=(6, 14)); row += 1
        opt_f.columnconfigure(0, weight=1)
        opt_f.columnconfigure(1, weight=1)

        # 보컬 타입
        voc_f = ttk.LabelFrame(opt_f, text=" 보컬 타입 ", padding=(10, 8))
        voc_f.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.var_vocal = tk.StringVar(value=self.cfg["vocal_type"])
        for val, lbl in [("female", "여성 👩"), ("male", "남성 👨"), ("none", "없음 🎸")]:
            ttk.Radiobutton(voc_f, text=lbl, variable=self.var_vocal,
                            value=val, style="TRadiobutton").pack(
                anchor="w", pady=2)

        # 생성 설정
        gen_f = ttk.LabelFrame(opt_f, text=" 생성 설정 ", padding=(10, 8))
        gen_f.grid(row=0, column=1, sticky="nsew")

        cnt_row = ttk.Frame(gen_f)
        cnt_row.pack(fill="x", pady=(0, 6))
        ttk.Label(cnt_row, text="곡 수:", font=F_LABEL).pack(side="left")
        self.var_count = tk.IntVar(value=self.cfg["songs_count"])
        ttk.Spinbox(cnt_row, from_=1, to=20, textvariable=self.var_count,
                    width=4, font=F_LABEL).pack(side="left", padx=(6, 4))
        ttk.Label(cnt_row, text="곡", font=F_LABEL).pack(side="left")

        self._lbl(gen_f, "선택 방식", 0)
        self.var_select = tk.StringVar(value=self.cfg["default_select"])
        for val, lbl in [("longest", "가장 긴 곡 자동"), ("random", "랜덤 1곡"), ("manual", "수동 선택")]:
            ttk.Radiobutton(gen_f, text=lbl, variable=self.var_select,
                            value=val).pack(anchor="w", pady=1)

    # ── 탭 2: YouTube ─────────────────────────────────────

    def _build_tab_youtube(self, nb):
        sf = ScrollableFrame(nb)
        nb.add(sf, text="  YouTube  ")
        tab = sf.inner
        tab.columnconfigure(0, weight=1)
        row = 0

        # ── 자동 업로드 토글 ─────────────────────────────
        self._lbl(tab, "📺  YouTube 자동 업로드", row); row += 1
        self.var_yt_upload = tk.BooleanVar(value=self.cfg["youtube_auto_upload"])
        ttk.Checkbutton(tab,
                        text="곡 처리 완료 후 자동으로 YouTube에 업로드",
                        variable=self.var_yt_upload,
                        command=self._toggle_yt).grid(
            row=row, column=0, sticky="w", pady=(2, 14)); row += 1

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── OAuth 인증 ──────────────────────────────────
        self._lbl(tab, "🔐  Google OAuth 인증", row); row += 1
        ttk.Label(tab, text="Google Cloud Console에서 발급한 client_secrets.json 파일 경로",
                  style="Hint.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)); row += 1

        sec_f = ttk.Frame(tab)
        sec_f.grid(row=row, column=0, sticky="ew", pady=(0, 6)); row += 1
        sec_f.columnconfigure(0, weight=1)
        self.var_secrets = tk.StringVar(value=self.cfg["youtube_client_secrets"])
        ttk.Entry(sec_f, textvariable=self.var_secrets, font=F_ENTRY).grid(
            row=0, column=0, sticky="ew")
        ttk.Button(sec_f, text="찾기", width=7,
                   command=self._browse_secrets).grid(row=0, column=1, padx=(6, 0))

        self._yt_auth_btn = ttk.Button(tab,
            text="🔑 YouTube 계정 인증 (브라우저로 열림)",
            command=self._run_yt_auth)
        self._yt_auth_btn.grid(row=row, column=0, sticky="w", pady=(0, 14)); row += 1

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── 채널 스타일 분석 ─────────────────────────────
        self._lbl(tab, "🔍  채널 스타일 분석", row); row += 1
        ttk.Label(tab, text="참고할 YouTube 채널 URL을 입력하면 제목/설명 스타일을 학습합니다.",
                  style="Hint.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)); row += 1

        ch_f = ttk.Frame(tab)
        ch_f.grid(row=row, column=0, sticky="ew", pady=(0, 4)); row += 1
        ch_f.columnconfigure(0, weight=1)
        self.var_channel_url = tk.StringVar(value=self.cfg["youtube_channel_url"])
        ch_entry = ttk.Entry(ch_f, textvariable=self.var_channel_url, font=F_ENTRY)
        ch_entry.grid(row=0, column=0, sticky="ew")
        self._analyze_btn = ttk.Button(ch_f, text="분석", width=6,
                                        command=self._analyze_channel)
        self._analyze_btn.grid(row=0, column=1, padx=(6, 0))

        # 플레이스홀더 흉내
        if not self.var_channel_url.get():
            _ph = "https://www.youtube.com/@channelname"
            ch_entry.insert(0, _ph)
            ch_entry.configure(foreground="#999999")
            def _fi(e, entry=ch_entry, ph=_ph):
                if entry.get() == ph:
                    entry.delete(0, "end")
                    entry.configure(foreground="")
            def _fo(e, entry=ch_entry, ph=_ph):
                if not entry.get():
                    entry.insert(0, ph)
                    entry.configure(foreground="#999999")
            ch_entry.bind("<FocusIn>", _fi)
            ch_entry.bind("<FocusOut>", _fo)

        style_info = self.cfg.get("youtube_channel_style", {})
        status_text = (f"✅ 분석됨: {style_info.get('style_notes', '')[:50]}"
                       if style_info else "⚠  아직 분석되지 않음")
        status_fg = "#2a7a2a" if style_info else "#888888"
        self._channel_status = ttk.Label(tab, text=status_text,
                                          foreground=status_fg, font=F_SMALL)
        self._channel_status.grid(row=row, column=0, sticky="w",
                                   pady=(0, 14)); row += 1

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── 플레이리스트 + 공개 범위 ─────────────────────
        self._lbl(tab, "📋  플레이리스트 & 공개 설정", row); row += 1

        pl_f = ttk.Frame(tab)
        pl_f.grid(row=row, column=0, sticky="ew", pady=(6, 0)); row += 1
        pl_f.columnconfigure(0, weight=1)
        pl_f.columnconfigure(1, weight=1)

        # 플레이리스트 ID
        pid_f = ttk.LabelFrame(pl_f, text=" 플레이리스트 ID (선택) ", padding=(10, 8))
        pid_f.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        pid_f.columnconfigure(0, weight=1)
        self.var_playlist = tk.StringVar(value=self.cfg["youtube_playlist_id"])
        ttk.Entry(pid_f, textvariable=self.var_playlist, font=F_MONO).grid(
            row=0, column=0, sticky="ew")
        ttk.Label(pid_f,
                  text="YouTube Studio → 재생목록 URL의\n?list= 뒤 값",
                  style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))

        # 공개 범위
        priv_f = ttk.LabelFrame(pl_f, text=" 공개 범위 ", padding=(10, 8))
        priv_f.grid(row=0, column=1, sticky="nsew")
        self.var_privacy = tk.StringVar(value=self.cfg["youtube_privacy"])
        for val, lbl, desc in [
            ("public",   "🌍 공개",   "누구나 볼 수 있음"),
            ("unlisted", "🔗 미등재",  "링크가 있으면 볼 수 있음"),
            ("private",  "🔒 비공개", "본인만 볼 수 있음"),
        ]:
            rf = ttk.Frame(priv_f)
            rf.pack(fill="x", pady=2)
            ttk.Radiobutton(rf, text=lbl, variable=self.var_privacy,
                            value=val).pack(side="left")
            ttk.Label(rf, text=desc, style="Hint.TLabel").pack(side="left", padx=(4, 0))

        self._toggle_yt()

    # ── 탭 3: 고급 설정 ──────────────────────────────────

    def _build_tab_advanced(self, nb):
        sf = ScrollableFrame(nb)
        nb.add(sf, text="  고급 설정  ")
        tab = sf.inner
        tab.columnconfigure(0, weight=1)
        row = 0

        # ── 예약 실행 ────────────────────────────────────
        self._lbl(tab, "⏰  예약 자동 실행", row); row += 1
        ttk.Label(tab, text="설정한 시간에 대기 중인 프로젝트를 자동으로 처리합니다.",
                  style="Hint.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)); row += 1

        sched_f = ttk.LabelFrame(tab, text=" 예약 설정 ", padding=(12, 10))
        sched_f.grid(row=row, column=0, sticky="ew", pady=(0, 14)); row += 1

        # 활성화 토글
        self.var_sched_on = tk.BooleanVar(value=self.cfg["schedule_enabled"])
        ttk.Checkbutton(sched_f, text="예약 실행 활성화",
                        variable=self.var_sched_on,
                        command=self._toggle_schedule).pack(anchor="w", pady=(0, 8))

        # 시간 선택
        time_f = ttk.Frame(sched_f)
        time_f.pack(fill="x", pady=(0, 8))
        ttk.Label(time_f, text="실행 시간:", font=F_LABEL).pack(side="left")

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
                                      values=hours, width=5, state="readonly",
                                      font=F_LABEL)
        self._hour_cb.pack(side="left", padx=(8, 0))
        ttk.Label(time_f, text=" : ", font=F_LABEL).pack(side="left")
        self._min_cb = ttk.Combobox(time_f, textvariable=self.var_minute,
                                     values=minutes, width=5, state="readonly",
                                     font=F_LABEL)
        self._min_cb.pack(side="left")

        # 요일 체크박스
        day_f = ttk.Frame(sched_f)
        day_f.pack(fill="x")
        ttk.Label(day_f, text="반복 요일:", font=F_LABEL).pack(side="left")
        saved_days = self.cfg.get("schedule_days", [d for d, _ in DAYS_KR])
        self._day_vars = {}
        self._day_cbs = []
        for key, label in DAYS_KR:
            v = tk.BooleanVar(value=(key in saved_days))
            self._day_vars[key] = v
            cb = ttk.Checkbutton(day_f, text=label, variable=v)
            cb.pack(side="left", padx=(6, 0))
            self._day_cbs.append(cb)

        self._toggle_schedule()

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── UI 좌표 학습 ─────────────────────────────────
        self._lbl(tab, "🎯  Suno UI 좌표 학습", row); row += 1
        ttk.Label(tab,
                  text="처음 실행 시 또는 Suno 화면이 바뀌었을 때 실행하세요.\n"
                       "마우스로 각 UI 요소의 위치를 기록합니다.",
                  style="Hint.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 8)); row += 1

        learn_f = ttk.Frame(tab)
        learn_f.grid(row=row, column=0, sticky="ew", pady=(0, 6)); row += 1
        learn_f.columnconfigure(0, weight=1)
        learn_f.columnconfigure(1, weight=1)

        ttk.Button(learn_f, text="🎬 녹화 학습\n(자연스럽게 진행하며 마킹)",
                   command=self._run_learn_record).grid(
            row=0, column=0, sticky="ew", padx=(0, 6), ipady=6)
        ttk.Button(learn_f, text="🖱 수동 학습\n(요소별 마우스 클릭)",
                   command=self._run_learn_manual).grid(
            row=0, column=1, sticky="ew", ipady=6)

        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, sticky="ew", pady=(12, 12)); row += 1

        # ── 로그 ─────────────────────────────────────────
        self._lbl(tab, "📋  실행 로그", row); row += 1
        log_f = ttk.Frame(tab)
        log_f.grid(row=row, column=0, sticky="ew", pady=(4, 0)); row += 1
        ttk.Button(log_f, text="📋 로그 파일 열기",
                   command=self._open_log).pack(side="left", padx=(0, 8))
        ttk.Label(log_f, text=f"위치: {Path.home() / '.suno_auto.log'}",
                  style="Hint.TLabel").pack(side="left")

    # ── 탭 4: 도움말 ──────────────────────────────────────

    def _build_tab_help(self, nb):
        sf = ScrollableFrame(nb)
        nb.add(sf, text="  도움말  ")
        tab = sf.inner
        tab.columnconfigure(0, weight=1)
        row = 0

        HELP_SECTIONS = [
            ("🚀  처음 시작하기 (순서대로 진행)", [
                "① [기본 설정] 탭 → Anthropic API 키 입력 (sk-ant-... 형식)",
                "② [고급 설정] 탭 → 🎬 녹화 학습 또는 🖱 수동 학습 실행",
                "③ [기본 설정] 탭 → 프로젝트 폴더 확인 후 저장",
                "④ 메뉴바 🎵 아이콘 → 📂 입력 폴더 열기 → 이미지 파일 넣기",
                "⑤ 메뉴바 🎵 아이콘 → ▶ 지금 실행",
            ]),
            ("📁  입력 파일 규칙", [
                "• 지원 형식: JPG, JPEG, PNG, WEBP",
                "• 파일명이 곡의 키워드가 됩니다.",
                "  예) sunset_calm.jpg → 키워드: 'sunset calm'",
                "  예) 01_도시의밤.jpg → 키워드: '도시의 밤'",
                "• 앞의 숫자+구분자는 자동으로 제거됩니다.",
                "• 파일 1개 = 프로젝트 1개 (곡 생성 1회)",
            ]),
            ("🎵  자동화 흐름 (4단계)", [
                "1단계: Claude AI가 이미지+키워드로 가사/스타일 생성",
                "2단계: pyautogui가 Suno 웹사이트를 자동 조작해 MP3 생성",
                "3단계: FFmpeg가 MP3+커버이미지를 YouTube용 MP4로 변환",
                "4단계: (선택) YouTube Data API로 자동 업로드",
            ]),
            ("🎯  UI 좌표 학습이 필요한 경우", [
                "• 앱을 처음 설치했을 때",
                "• Suno 웹사이트 UI가 변경되었을 때",
                "• '❌ 학습 데이터 불완전' 오류가 발생했을 때",
                "",
                "학습 방법:",
                "  [녹화 학습] — Suno 페이지를 열고 자연스럽게 사용하면서",
                "                  숫자 키(1~7)로 각 버튼 위치를 마킹",
                "  [수동 학습] — 각 요소 위로 마우스를 올리고 Enter 입력",
            ]),
            ("📺  YouTube 업로드 설정", [
                "① Google Cloud Console (console.cloud.google.com) 접속",
                "② 새 프로젝트 생성 → YouTube Data API v3 활성화",
                "③ OAuth 2.0 클라이언트 ID 생성 → client_secrets.json 다운로드",
                "④ [YouTube] 탭 → 파일 경로 입력 → 🔑 인증 버튼 클릭",
                "⑤ 브라우저에서 Google 계정 로그인 및 권한 허용",
            ]),
            ("⚠️  주의 사항", [
                "• Suno 이용약관상 자동화 사용이 제한될 수 있습니다.",
                "• 개인 학습/연구 용도로만 사용하세요.",
                "• 화면이 켜져 있어야 pyautogui 자동화가 작동합니다.",
                "• MacOS: 시스템 설정 → 개인정보 보호 → 접근성에서 앱 허용 필요",
                "• MacOS: 화면 기록 권한도 필요합니다 (UI 변경 감지 기능).",
            ]),
            ("🔧  문제 해결", [
                "• 앱이 실행 안 될 때: 터미널에서 python suno_menu_bar.py 실행 후 오류 확인",
                "• UI 조작 실패: 고급 설정 → UI 좌표 재학습",
                "• API 오류: API 키 유효성 및 잔액 확인 (console.anthropic.com)",
                "• 다운로드 실패: Suno 로그인 상태 확인, 크롬 브라우저 설치 확인",
                "• 로그 확인: 고급 설정 → 📋 로그 파일 열기",
            ]),
        ]

        for title, items in HELP_SECTIONS:
            lf = ttk.LabelFrame(tab, text=f"  {title}  ", padding=(12, 10))
            lf.grid(row=row, column=0, sticky="ew", pady=(0, 10)); row += 1
            lf.columnconfigure(0, weight=1)
            for item in items:
                if item == "":
                    ttk.Label(lf, text="").pack(anchor="w")
                else:
                    ttk.Label(lf, text=item, font=F_LABEL,
                              wraplength=550, justify="left").pack(
                        anchor="w", pady=1)

    # ── 헬퍼 ──────────────────────────────────────────────

    def _lbl(self, parent, text, row=None):
        lbl = ttk.Label(parent, text=text, style="Section.TLabel")
        if row is not None:
            lbl.grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))
        else:
            lbl.pack(anchor="w", pady=(10, 0))
        return lbl

    # ── 콜백 ──────────────────────────────────────────────

    def _toggle_api_show(self):
        """API 키 표시/숨기기 토글."""
        current = self._api_entry.cget("show")
        self._api_entry.configure(show="" if current == "*" else "*")

    def _paste_api(self):
        try:
            text = self.root.clipboard_get().strip()
            if text:
                self.var_api.set(text)
            else:
                messagebox.showwarning("붙여넣기", "클립보드가 비어 있습니다.")
        except Exception:
            messagebox.showerror("오류", "클립보드에 접근할 수 없습니다.")

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
        self._analyze_btn.configure(state=state)

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
            self._channel_status.configure(
                text=f"✅ 분석됨: {notes}", foreground="#2a7a2a")
            messagebox.showinfo("분석 완료",
                                f"채널 스타일 분석 완료!\n\n{style.get('style_notes','')}")
        except Exception as e:
            messagebox.showerror("분석 실패", str(e))
        finally:
            self._analyze_btn.configure(state="normal", text="분석")

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
        # API 키 기본 검증
        api_key = self.var_api.get().strip()
        if not quiet and api_key and not api_key.startswith("sk-ant-"):
            if not messagebox.askyesno("API 키 확인",
                                       "입력한 API 키가 'sk-ant-'로 시작하지 않습니다.\n"
                                       "올바른 Anthropic API 키인지 확인하세요.\n\n"
                                       "그래도 저장하시겠습니까?"):
                return

        # 예약 시간 조합
        schedule_time = ""
        if self.var_sched_on.get():
            schedule_time = f"{self.var_hour.get()}:{self.var_minute.get()}"

        schedule_days = [k for k, v in self._day_vars.items() if v.get()]

        # channel_url에서 플레이스홀더 값 제거
        channel_url = self.var_channel_url.get().strip()
        if channel_url == "https://www.youtube.com/@channelname":
            channel_url = ""

        cfg = {
            **self.cfg,
            "anthropic_api_key":      api_key,
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
            "youtube_channel_url":    channel_url,
        }
        save_config(cfg)
        self.cfg = cfg  # 로컬 캐시도 갱신
        if not quiet:
            messagebox.showinfo("저장 완료", "✅ 설정이 저장되었습니다.")
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help-tab", action="store_true")
    args, _ = parser.parse_known_args()

    win = SettingsWindow()
    if args.help_tab:
        # 도움말 탭(마지막 탭)으로 바로 이동
        try:
            nb = win.root.winfo_children()[0]  # Notebook
            nb.select(3)  # 4번째 탭 = 도움말
        except Exception:
            pass
    win.run()
