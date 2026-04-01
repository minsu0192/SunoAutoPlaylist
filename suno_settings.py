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
from tkinter import filedialog, font, messagebox, ttk

CONFIG_FILE = Path.home() / ".suno_config.json"

DEFAULTS = {
    "anthropic_api_key":        "",
    "projects_root":            str(Path.home() / "SunoProjects"),
    "default_style":            "cinematic, orchestral, emotional",
    "vocal_type":               "female",
    "default_select":           "longest",
    "songs_count":              2,
    "schedule_time":            "",
    "youtube_auto_upload":      False,
    "youtube_client_secrets":   "",
    "youtube_playlist_id":      "",
    "youtube_privacy":          "public",
}

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


# ────────────────────────────────────────────────────────────
# 메인 설정 창
# ────────────────────────────────────────────────────────────

class SettingsWindow:

    def __init__(self):
        self.cfg = load_config()

        self.root = tk.Tk()
        self.root.title("수노 자동화 설정")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)

        # 창 크기 & 중앙 배치
        W, H = 620, 560
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.root.minsize(560, 480)

        # macOS 붙여넣기 단축키 패치
        self._patch_paste()

        self._build_ui()

    # ── 붙여넣기 패치 ──────────────────────────────────────

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

    # ── UI 빌드 ───────────────────────────────────────────

    def _build_ui(self):
        # 노트북(탭)
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self._build_tab_basic(nb)
        self._build_tab_youtube(nb)
        self._build_tab_advanced(nb)

        # 저장 / 취소 버튼
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
        self._label(tab, "Anthropic API 키", row); row += 1
        self.var_api = tk.StringVar(value=self.cfg["anthropic_api_key"])
        api_f = ttk.Frame(tab)
        api_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 10)); row += 1
        ttk.Entry(api_f, textvariable=self.var_api, show="*",
                  font=("Menlo", 12)).pack(side="left", fill="x", expand=True)
        ttk.Button(api_f, text="붙여넣기",
                   command=self._paste_api).pack(side="left", padx=(6, 0))

        # 입력 폴더
        self._label(tab, "입력 폴더 (이미지를 여기에 넣으세요)", row); row += 1
        self.var_root = tk.StringVar(value=self.cfg["projects_root"])
        root_f = ttk.Frame(tab)
        root_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 10)); row += 1
        ttk.Entry(root_f, textvariable=self.var_root,
                  font=("Helvetica", 12)).pack(side="left", fill="x", expand=True)
        ttk.Button(root_f, text="찾기",
                   command=self._browse_folder).pack(side="left", padx=(6, 0))

        # 음악 스타일
        self._label(tab, "음악 스타일", row); row += 1
        style_f = ttk.Frame(tab)
        style_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 4)); row += 1

        self.var_preset = tk.StringVar(value="직접 입력")
        preset_labels = [p[0] for p in STYLE_PRESETS]
        preset_cb = ttk.Combobox(style_f, textvariable=self.var_preset,
                                 values=preset_labels, state="readonly", width=18)
        preset_cb.pack(side="left")
        preset_cb.bind("<<ComboboxSelected>>", self._on_preset)

        self.var_style = tk.StringVar(value=self.cfg["default_style"])
        ttk.Entry(tab, textvariable=self.var_style,
                  font=("Helvetica", 12)).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)); row += 1

        # 보컬 타입
        self._label(tab, "보컬 타입", row); row += 1
        self.var_vocal = tk.StringVar(value=self.cfg["vocal_type"])
        vf = ttk.Frame(tab)
        vf.grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 10)); row += 1
        for val, lbl in [("female", "여성"), ("male", "남성"), ("none", "없음")]:
            ttk.Radiobutton(vf, text=lbl, variable=self.var_vocal,
                            value=val).pack(side="left", padx=10)

        # 생성 곡 수 + 선택 방식
        counts_f = ttk.Frame(tab)
        counts_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)); row += 1

        # 곡 수
        left = ttk.LabelFrame(counts_f, text="한 번에 생성할 곡 수", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.var_count = tk.IntVar(value=self.cfg["songs_count"])
        for n in range(1, 5):
            ttk.Radiobutton(left, text=f"{n}곡", variable=self.var_count,
                            value=n).pack(side="left", padx=6)

        # 선택 방식
        right = ttk.LabelFrame(counts_f, text="곡 선택 방식", padding=8)
        right.pack(side="left", fill="both", expand=True)
        self.var_select = tk.StringVar(value=self.cfg["default_select"])
        for val, lbl in [("longest", "가장 긴 곡"), ("random", "랜덤"), ("manual", "수동")]:
            ttk.Radiobutton(right, text=lbl, variable=self.var_select,
                            value=val).pack(side="left", padx=6)

        tab.columnconfigure(0, weight=1)

    # ── 탭 2: YouTube ─────────────────────────────────────

    def _build_tab_youtube(self, nb):
        tab = ttk.Frame(nb, padding=16)
        nb.add(tab, text="  YouTube  ")

        row = 0

        # 자동 업로드 토글
        self.var_yt_upload = tk.BooleanVar(value=self.cfg["youtube_auto_upload"])
        ttk.Checkbutton(tab, text="완료 후 자동으로 YouTube에 업로드",
                        variable=self.var_yt_upload,
                        command=self._toggle_yt).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 12)); row += 1

        # OAuth 파일
        self._label(tab, "Google OAuth 인증 파일 (client_secrets.json)", row); row += 1
        oauth_f = ttk.Frame(tab)
        oauth_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 4)); row += 1
        self.var_secrets = tk.StringVar(value=self.cfg["youtube_client_secrets"])
        self._secrets_entry = ttk.Entry(oauth_f, textvariable=self.var_secrets,
                                        font=("Helvetica", 11))
        self._secrets_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(oauth_f, text="찾기",
                   command=self._browse_secrets).pack(side="left", padx=(6, 0))

        # 인증 버튼
        self._yt_auth_btn = ttk.Button(tab, text="🔑 YouTube 계정 인증 (브라우저 열림)",
                                       command=self._run_yt_auth)
        self._yt_auth_btn.grid(row=row, column=0, columnspan=2,
                               sticky="w", pady=(0, 16)); row += 1

        # 구분선
        ttk.Separator(tab).grid(row=row, column=0, columnspan=2,
                                sticky="ew", pady=8); row += 1

        # 플레이리스트 ID
        self._label(tab, "플레이리스트 ID (선택 사항)", row); row += 1
        self.var_playlist = tk.StringVar(value=self.cfg["youtube_playlist_id"])
        ttk.Entry(tab, textvariable=self.var_playlist,
                  font=("Helvetica", 12)).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(2, 10)); row += 1

        # 공개 범위
        self._label(tab, "공개 범위", row); row += 1
        self.var_privacy = tk.StringVar(value=self.cfg["youtube_privacy"])
        pf = ttk.Frame(tab)
        pf.grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 10)); row += 1
        for val, lbl in [("public", "공개"), ("unlisted", "미등재"), ("private", "비공개")]:
            ttk.Radiobutton(pf, text=lbl, variable=self.var_privacy,
                            value=val).pack(side="left", padx=10)

        # 안내
        info = ("ⓘ Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 만들고\n"
                "   client_secrets.json 파일을 다운로드해서 위에서 선택하세요.\n"
                "   처음 인증 시 브라우저가 열리고, 이후에는 자동 로그인됩니다.")
        ttk.Label(tab, text=info, foreground="#666",
                  font=("Helvetica", 10), justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 0)); row += 1

        self._toggle_yt()
        tab.columnconfigure(0, weight=1)

    # ── 탭 3: 고급 설정 ──────────────────────────────────

    def _build_tab_advanced(self, nb):
        tab = ttk.Frame(nb, padding=16)
        nb.add(tab, text="  고급 설정  ")

        row = 0

        # 예약 실행
        self._label(tab, "예약 실행 시간 (HH:MM — 비우면 예약 없음)", row); row += 1
        self.var_schedule = tk.StringVar(value=self.cfg["schedule_time"])
        ttk.Entry(tab, textvariable=self.var_schedule, width=10,
                  font=("Helvetica", 13)).grid(
            row=row, column=0, sticky="w", pady=(2, 12)); row += 1

        ttk.Separator(tab).grid(row=row, column=0, columnspan=2,
                                sticky="ew", pady=8); row += 1

        # UI 재학습
        self._label(tab, "Suno UI 좌표 재학습", row); row += 1
        ttk.Label(tab,
                  text="Suno 화면이 바뀌었거나 처음 설정할 때 실행하세요.",
                  foreground="#666", font=("Helvetica", 11)).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 6)); row += 1

        btn_f = ttk.Frame(tab)
        btn_f.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 12)); row += 1
        ttk.Button(btn_f, text="🤖 자동 재학습 (Claude Vision)",
                   command=self._run_learn_auto).pack(side="left", padx=(0, 8))
        ttk.Button(btn_f, text="🖱 수동 재학습 (직접 클릭)",
                   command=self._run_learn_manual).pack(side="left")

        ttk.Separator(tab).grid(row=row, column=0, columnspan=2,
                                sticky="ew", pady=8); row += 1

        # 로그 보기
        self._label(tab, "최근 실행 로그", row); row += 1
        ttk.Button(tab, text="📋 로그 파일 열기",
                   command=self._open_log).grid(
            row=row, column=0, sticky="w", pady=(2, 0)); row += 1

        tab.columnconfigure(0, weight=1)

    # ── 헬퍼 위젯 ────────────────────────────────────────

    def _label(self, parent, text, row):
        ttk.Label(parent, text=text,
                  font=("Helvetica", 12, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))

    # ── 콜백 ─────────────────────────────────────────────

    def _paste_api(self):
        try:
            text = self.root.clipboard_get()
            self.var_api.set(text.strip())
        except Exception:
            messagebox.showerror("오류", "클립보드가 비어 있거나 접근할 수 없습니다.")

    def _browse_folder(self):
        d = filedialog.askdirectory(title="입력 폴더 선택",
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
        selected = self.var_preset.get()
        for name, style in STYLE_PRESETS:
            if name == selected and style:
                self.var_style.set(style)
                break

    def _toggle_yt(self):
        state = "normal" if self.var_yt_upload.get() else "disabled"
        self._yt_auth_btn.configure(state=state)

    def _run_yt_auth(self):
        secrets = self.var_secrets.get().strip()
        if not secrets or not Path(secrets).exists():
            messagebox.showerror("오류",
                                 "먼저 client_secrets.json 파일을 선택하세요.")
            return
        script_dir = Path(__file__).parent
        subprocess.Popen([sys.executable,
                          str(script_dir / "youtube_upload.py"),
                          "--auth-only",
                          "--secrets", secrets])
        messagebox.showinfo("YouTube 인증",
                            "브라우저가 열렸습니다.\n구글 계정으로 로그인하고 허용을 클릭하세요.")

    def _run_learn_auto(self):
        self._save(quiet=True)
        script_dir = Path(__file__).parent
        subprocess.Popen([sys.executable,
                          str(script_dir / "suno_learn.py"), "--force"])
        messagebox.showinfo("UI 재학습",
                            "터미널 창이 열립니다.\nsuno.com/create → Advanced 탭을 열고\nEnter를 눌러 학습을 시작하세요.")

    def _run_learn_manual(self):
        self._save(quiet=True)
        script_dir = Path(__file__).parent
        subprocess.Popen([sys.executable,
                          str(script_dir / "suno_learn.py"), "--manual"])
        messagebox.showinfo("UI 수동 학습",
                            "터미널 창이 열립니다.\n각 요소 위에 마우스를 올리고 Enter를 누르세요.")

    def _open_log(self):
        log = Path.home() / ".suno_auto.log"
        if log.exists():
            subprocess.Popen(["open", str(log)])
        else:
            messagebox.showinfo("로그", "아직 로그가 없습니다.")

    # ── 저장 ─────────────────────────────────────────────

    def _save(self, quiet: bool = False):
        schedule = self.var_schedule.get().strip()
        if schedule and not re.match(r"^\d{1,2}:\d{2}$", schedule):
            messagebox.showerror("오류",
                                 "예약 시간 형식이 잘못됐습니다.\n예시: 02:00 또는 14:30")
            return

        cfg = {
            "anthropic_api_key":      self.var_api.get().strip(),
            "projects_root":          self.var_root.get().strip(),
            "default_style":          self.var_style.get().strip(),
            "vocal_type":             self.var_vocal.get(),
            "default_select":         self.var_select.get(),
            "songs_count":            self.var_count.get(),
            "schedule_time":          schedule,
            "youtube_auto_upload":    self.var_yt_upload.get(),
            "youtube_client_secrets": self.var_secrets.get().strip(),
            "youtube_playlist_id":    self.var_playlist.get().strip(),
            "youtube_privacy":        self.var_privacy.get(),
        }
        save_config(cfg)
        if not quiet:
            messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SettingsWindow().run()
