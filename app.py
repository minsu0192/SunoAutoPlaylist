"""
app.py — 수노자동화 메인 GUI
"""

from __future__ import annotations

import os
import subprocess
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import Config
from queue_manager import QueueManager, STATUS_DONE, STATUS_FAILED, STATUS_PENDING, STATUS_PROCESSING

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACTIONS_FILE = Path.home() / ".suno_actions.json"
ACCENT = "#8B5CF6"  # 보라색 액센트


# ================================================================== #
# Cmd+V 패치                                                          #
# ================================================================== #

def _patch_paste(root):
    def paste(event):
        try:
            w = event.widget
            try:
                w.delete("sel.first", "sel.last")
            except Exception:
                pass
            w.insert("insert", root.clipboard_get())
        except Exception:
            pass
        return "break"
    def select_all(event):
        try:
            event.widget.select_range(0, "end")
            event.widget.icursor("end")
        except Exception:
            pass
        return "break"
    root.bind_class("Entry", "<Command-v>", paste)
    root.bind_class("Entry", "<Command-a>", select_all)


# ================================================================== #
# 설정 창                                                              #
# ================================================================== #

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, config: Config, on_save):
        super().__init__(parent)
        self.title("설정")
        self.geometry("520x640")
        self.resizable(False, False)
        self.grab_set()
        self.after(100, self.lift)
        self._config = config
        self._on_save = on_save
        self._vars = {}
        self._build()

    def _section(self, parent, title):
        ctk.CTkLabel(parent, text=title, font=("", 14, "bold"),
                      text_color=ACCENT).pack(anchor="w", pady=(12, 6))

    def _build(self):
        m = ctk.CTkScrollableFrame(self)
        m.pack(fill="both", expand=True, padx=20, pady=16)

        # ── API 키
        self._section(m, "API 키")
        v_api = ctk.StringVar(value=self._config.anthropic_api_key)
        self._vars["anthropic_api_key"] = v_api
        row = ctk.CTkFrame(m, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkEntry(row, textvariable=v_api, height=36, placeholder_text="sk-ant-...").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row, text="붙여넣기", width=80, height=36, fg_color="gray30",
                       command=lambda: v_api.set(self._safe_clipboard())).pack(side="right")

        # ── 곡 설정
        self._section(m, "곡 수")
        row = ctk.CTkFrame(m, fg_color="transparent")
        row.pack(fill="x")
        for label, key, default in [("한국어", "korean_songs", self._config.korean_songs),
                                     ("영어", "english_songs", self._config.english_songs),
                                     ("Inst.", "instrumental_songs", self._config.instrumental_songs)]:
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", expand=True, fill="x", padx=(0, 6))
            ctk.CTkLabel(col, text=label, font=("", 12)).pack(anchor="w")
            v = ctk.IntVar(value=default)
            self._vars[key] = v
            ctk.CTkEntry(col, textvariable=v, height=34, width=60).pack(anchor="w", pady=(2, 0))

        # ── 보컬 선택
        self._section(m, "보컬곡 선택 (2곡 중)")
        v_pick = ctk.StringVar(value=self._config.vocal_pick)
        self._vars["vocal_pick"] = v_pick
        ctk.CTkSegmentedButton(m, values=["longer", "shorter", "random", "both"], variable=v_pick).pack(fill="x")
        ctk.CTkLabel(m, text="longer=긴 곡 | shorter=짧은 곡 | random=랜덤 1곡 | both=2곡 다",
                      font=("", 10), text_color="gray50").pack(anchor="w", pady=(2, 0))

        # ── 실행 범위
        self._section(m, "실행 범위")
        v_scope = ctk.StringVar(value=self._config.pipeline_scope)
        self._vars["pipeline_scope"] = v_scope
        ctk.CTkSegmentedButton(m, values=["songs", "videos", "upload"], variable=v_scope).pack(fill="x")
        ctk.CTkLabel(m, text="songs=곡만 | videos=+영상 | upload=+YouTube",
                      font=("", 10), text_color="gray50").pack(anchor="w", pady=(2, 0))

        # ── Pixabay (이미지 자동 다운로드)
        self._section(m, "Pixabay (이미지 자동)")
        v_pix = ctk.StringVar(value=self._config.pixabay_api_key)
        self._vars["pixabay_api_key"] = v_pix
        ctk.CTkEntry(m, textvariable=v_pix, height=34,
                      placeholder_text="Pixabay API 키 (없으면 비워두기)").pack(fill="x")
        ctk.CTkLabel(m, text="키워드로 영상 배경 이미지 자동 검색. pixabay.com에서 무료 발급",
                      font=("", 10), text_color="gray50").pack(anchor="w", pady=(2, 0))

        # ── YouTube
        self._section(m, "YouTube")
        yt_row = ctk.CTkFrame(m, fg_color="transparent")
        yt_row.pack(fill="x")
        v_yt = ctk.StringVar(value=self._config.youtube_client_secrets)
        self._vars["youtube_client_secrets"] = v_yt
        ctk.CTkEntry(yt_row, textvariable=v_yt, height=34, placeholder_text="client_secrets.json").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(yt_row, text="선택", width=60, height=34,
                       command=self._pick_secrets).pack(side="right")

        v_pl = ctk.StringVar(value=self._config.youtube_playlist_id)
        self._vars["youtube_playlist_id"] = v_pl
        ctk.CTkEntry(m, textvariable=v_pl, height=34,
                      placeholder_text="플레이리스트 ID (선택)").pack(fill="x", pady=(6, 0))

        v_priv = ctk.StringVar(value=self._config.youtube_privacy)
        self._vars["youtube_privacy"] = v_priv
        ctk.CTkSegmentedButton(m, values=["public", "unlisted", "private"],
                                variable=v_priv).pack(fill="x", pady=(6, 0))

        ctk.CTkButton(m, text="Google 인증", height=34,
                       fg_color="#e74c3c", hover_color="#c0392b",
                       command=self._google_auth).pack(fill="x", pady=(6, 0))

        # ── 출력 폴더
        self._section(m, "출력 폴더")
        out_row = ctk.CTkFrame(m, fg_color="transparent")
        out_row.pack(fill="x")
        v_out = ctk.StringVar(value=self._config.output_dir)
        self._vars["output_dir"] = v_out
        ctk.CTkEntry(out_row, textvariable=v_out, height=34).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(out_row, text="선택", width=60, height=34,
                       command=lambda: v_out.set(filedialog.askdirectory() or v_out.get())).pack(side="right")

        # ── 저장/취소
        btn_row = ctk.CTkFrame(m, fg_color="transparent")
        btn_row.pack(fill="x", pady=(16, 0))
        ctk.CTkButton(btn_row, text="저장", height=40, fg_color=ACCENT,
                       command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="취소", height=40, fg_color="gray30",
                       command=self.destroy).pack(side="right")

    def _safe_clipboard(self):
        try:
            return self.clipboard_get().strip()
        except Exception:
            return ""

    def _pick_secrets(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p:
            self._vars["youtube_client_secrets"].set(p)

    def _google_auth(self):
        self._save(quiet=True)
        path = self._vars["youtube_client_secrets"].get().strip()
        if not path:
            messagebox.showwarning("경고", "client_secrets.json을 먼저 선택하세요.", parent=self)
            return
        try:
            from yt_upload import YouTubeUploader
            YouTubeUploader().authenticate(path)
            messagebox.showinfo("성공", "Google 인증 완료!", parent=self)
        except Exception as e:
            messagebox.showerror("실패", str(e), parent=self)

    def _save(self, quiet=False):
        try:
            c = self._config
            c.anthropic_api_key = self._vars["anthropic_api_key"].get().strip()
            c.pixabay_api_key = self._vars["pixabay_api_key"].get().strip()
            c.korean_songs = int(self._vars["korean_songs"].get())
            c.english_songs = int(self._vars["english_songs"].get())
            c.instrumental_songs = int(self._vars["instrumental_songs"].get())
            c.vocal_pick = self._vars["vocal_pick"].get()
            c.pipeline_scope = self._vars["pipeline_scope"].get()
            c.youtube_client_secrets = self._vars["youtube_client_secrets"].get().strip()
            c.youtube_playlist_id = self._vars["youtube_playlist_id"].get().strip()
            c.youtube_privacy = self._vars["youtube_privacy"].get()
            c.output_dir = self._vars["output_dir"].get().strip()
            c.save()
            self._on_save(c)
            if not quiet:
                self.destroy()
        except Exception as e:
            if not quiet:
                messagebox.showerror("저장 실패", str(e), parent=self)


# ================================================================== #
# 큐 카드                                                              #
# ================================================================== #

class QueueCard(ctk.CTkFrame):
    COLORS = {
        STATUS_PENDING: ("gray50", "gray22"),
        STATUS_PROCESSING: ("#f39c12", "#2a2000"),
        STATUS_DONE: ("#2ecc71", "#002a10"),
        STATUS_FAILED: ("#e74c3c", "#2a0000"),
    }

    def __init__(self, parent, item: dict, on_select=None):
        color, bg = self.COLORS.get(item["status"], ("gray50", "gray17"))
        super().__init__(parent, corner_radius=8, fg_color=bg, height=48)
        self.pack_propagate(False)
        self.item = item
        self._on_select = on_select
        self.bind("<Button-1>", self._click)

        # 상태 점
        dot = ctk.CTkLabel(self, text="●", font=("", 10), text_color=color, width=20)
        dot.pack(side="left", padx=(10, 4))
        dot.bind("<Button-1>", self._click)

        kw = ctk.CTkLabel(self, text=item["keyword"], font=("", 13, "bold"), anchor="w")
        kw.pack(side="left", fill="x", expand=True)
        kw.bind("<Button-1>", self._click)

        label = {STATUS_PENDING: "대기", STATUS_PROCESSING: "진행중",
                 STATUS_DONE: "완료", STATUS_FAILED: "실패"}.get(item["status"], "?")
        st = ctk.CTkLabel(self, text=label, font=("", 11), text_color=color, width=50)
        st.pack(side="right", padx=10)
        st.bind("<Button-1>", self._click)

    def _click(self, _=None):
        if self._on_select:
            self._on_select(self)

    def set_selected(self, val: bool):
        self.configure(border_width=2 if val else 0,
                       border_color=ACCENT if val else "transparent")


# ================================================================== #
# 메인 앱                                                              #
# ================================================================== #

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._config = Config.load()
        self._queue = QueueManager()
        self._running = False
        self._stop_flag = threading.Event()
        self._selected_card: QueueCard | None = None
        self._cards: list[QueueCard] = []

        self.title("수노자동화")
        self.geometry("600x650")
        self.minsize(500, 500)

        _patch_paste(self)
        self._build()
        self._refresh()

        if not self._config.anthropic_api_key:
            self.after(300, self._show_onboarding)
        else:
            self.after(500, self._check_accessibility)

    # ── 온보딩 ────────────────────────────────────────────────
    def _show_onboarding(self):
        messagebox.showinfo("환영합니다!",
            "1. 설정에서 API 키 입력\n2. UI 학습\n3. 이미지 추가 + 실행")
        self._on_settings()
        self.after(500, self._check_accessibility)

    def _check_accessibility(self):
        try:
            from suno_bot import check_accessibility
            if not check_accessibility():
                raise RuntimeError()
        except Exception:
            messagebox.showwarning("접근성 권한",
                "시스템 설정 → 개인정보 보호 → 접근성\n→ 수노자동화 추가 후 켜주세요")
            subprocess.Popen(["open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])

    # ── UI 빌드 ───────────────────────────────────────────────
    def _build(self):
        # ── 상단: 토글 바 (현재 설정 요약) ────────────────────
        top = ctk.CTkFrame(self, fg_color="gray14", corner_radius=0, height=44)
        top.pack(fill="x")
        top.pack_propagate(False)

        inner_top = ctk.CTkFrame(top, fg_color="transparent")
        inner_top.pack(expand=True)

        cfg = self._config
        scope_txt = {"songs": "곡만", "videos": "곡+영상", "upload": "전체"}.get(cfg.pipeline_scope, "?")
        total = cfg.korean_songs + cfg.english_songs + cfg.instrumental_songs

        pix = "IMG" if cfg.pixabay_api_key else ""
        self._top_label = ctk.CTkLabel(inner_top,
            text=f"KR {cfg.korean_songs} | EN {cfg.english_songs} | Inst {cfg.instrumental_songs} | {cfg.vocal_pick} | {scope_txt}" + (f" | {pix}" if pix else ""),
            font=("", 12), text_color="gray50")
        self._top_label.pack(side="left", padx=8)

        ctk.CTkButton(inner_top, text="설정", width=60, height=28, font=("", 11),
                       fg_color="gray25", hover_color="gray35",
                       command=self._on_settings).pack(side="right", padx=4)
        ctk.CTkButton(inner_top, text="UI 학습", width=70, height=28, font=("", 11),
                       fg_color="gray25", hover_color="gray35",
                       command=self._on_learn).pack(side="right", padx=4)

        # ── 키워드 입력 ───────────────────────────────────────
        kw_frame = ctk.CTkFrame(self, fg_color="transparent")
        kw_frame.pack(fill="x", padx=16, pady=(12, 4))

        self._kw_entry = ctk.CTkEntry(kw_frame, height=36, placeholder_text="키워드 입력 (예: lofi chill, 가을 감성)")
        self._kw_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._kw_entry.bind("<Return>", lambda _: self._add_keyword())

        ctk.CTkButton(kw_frame, text="추가", width=60, height=36, fg_color=ACCENT,
                       hover_color="#7C3AED", command=self._add_keyword).pack(side="right")

        # ── 이미지 추가 (영상 만들 때만 필요) ────────────────────
        self._drop_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="gray17",
                                         border_width=1, border_color="gray25", height=50)
        self._drop_frame.pack(fill="x", padx=16, pady=(0, 8))
        self._drop_frame.pack_propagate(False)
        self._drop_frame.bind("<Button-1>", lambda _: self._pick_files())

        self._drop_label = ctk.CTkLabel(self._drop_frame,
            text="이미지 추가 (영상 만들 때만 필요, 파일명 = 키워드)",
            font=("", 11), text_color="gray40", cursor="hand2")
        self._drop_label.pack(expand=True)
        self._drop_label.bind("<Button-1>", lambda _: self._pick_files())
        self._setup_dnd()

        # ── 큐 목록 헤더 ─────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(4, 2))
        ctk.CTkLabel(header, text="작업 목록", font=("", 12, "bold"),
                      text_color="gray55").pack(side="left")
        self._count_label = ctk.CTkLabel(header, text="0개", font=("", 11),
                                          text_color="gray45")
        self._count_label.pack(side="right")

        # ── 큐 스크롤 ────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        # ── 프로그래스 바 ─────────────────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        prog_frame.pack(fill="x", padx=16, pady=(0, 4), side="bottom")
        prog_frame.pack_propagate(False)

        self._progress_bar = ctk.CTkProgressBar(prog_frame, height=8,
                                                  progress_color=ACCENT)
        self._progress_bar.pack(fill="x", pady=(4, 0))
        self._progress_bar.set(0)

        self._progress_label = ctk.CTkLabel(prog_frame, text="",
                                             font=("", 11), text_color="gray50")
        self._progress_label.pack(fill="x", pady=(2, 0))

        # ── 하단 버튼 바 ─────────────────────────────────────
        bar = ctk.CTkFrame(self, fg_color="gray14", corner_radius=0, height=56)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(expand=True)

        self._btn_run = ctk.CTkButton(inner, text="실행", width=100, height=36,
                                       font=("", 13, "bold"), fg_color=ACCENT,
                                       hover_color="#7C3AED", command=self._on_run)
        self._btn_run.pack(side="left", padx=4)

        self._btn_stop = ctk.CTkButton(inner, text="중단", width=70, height=36,
                                        fg_color="#e74c3c", hover_color="#c0392b",
                                        command=self._on_stop, state="disabled")
        self._btn_stop.pack(side="left", padx=4)

        ctk.CTkButton(inner, text="삭제", width=70, height=36,
                       fg_color="gray25", hover_color="gray35",
                       command=self._on_delete).pack(side="left", padx=4)

        ctk.CTkButton(inner, text="로그", width=60, height=36,
                       fg_color="gray25", hover_color="gray35",
                       command=self._on_show_log).pack(side="left", padx=4)

    # ── DnD ───────────────────────────────────────────────────
    def _setup_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES
            for w in (self._drop_frame, self._drop_label):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
            self._drop_label.configure(text="이미지 드래그 또는 클릭 (파일명 = 키워드)")
        except Exception:
            self._setup_input_folder()

    def _setup_input_folder(self):
        self._input_dir = Path.home() / "SunoOutput" / "input"
        self._input_dir.mkdir(parents=True, exist_ok=True)
        self._drop_label.configure(text="클릭 또는 ~/SunoOutput/input/ 에 이미지 넣기")
        self._check_input_folder()

    def _check_input_folder(self):
        if hasattr(self, "_input_dir") and self._input_dir.exists():
            exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
            added = False
            for f in self._input_dir.iterdir():
                if f.suffix.lower() in exts:
                    self._add_image(str(f))
                    processed = self._input_dir / "processed"
                    processed.mkdir(exist_ok=True)
                    try:
                        f.rename(processed / f.name)
                    except Exception:
                        pass
                    added = True
            if added:
                self._refresh()
        self.after(5000, self._check_input_folder)

    # ── 상태/갱신 ─────────────────────────────────────────────
    def _update_top_bar(self):
        cfg = self._config
        scope_txt = {"songs": "곡만", "videos": "곡+영상", "upload": "전체"}.get(cfg.pipeline_scope, "?")
        pix = "IMG" if cfg.pixabay_api_key else ""
        self._top_label.configure(
            text=f"KR {cfg.korean_songs} | EN {cfg.english_songs} | Inst {cfg.instrumental_songs} | {cfg.vocal_pick} | {scope_txt}" + (f" | {pix}" if pix else ""))

    def _refresh(self):
        for c in self._cards:
            c.destroy()
        self._cards.clear()
        self._selected_card = None
        items = self._queue.get_all()
        self._count_label.configure(text=f"{len(items)}개")
        for item in items:
            card = QueueCard(self._scroll, item, on_select=self._select_card)
            card.pack(fill="x", pady=2)
            self._cards.append(card)
        if not self._running:
            self._progress_bar.set(0)
            pending = len(self._queue.get_pending())
            self._progress_label.configure(
                text=f"{pending}개 대기" if pending else "키워드를 입력하세요")

    def _select_card(self, card: QueueCard):
        if self._selected_card:
            self._selected_card.set_selected(False)
        self._selected_card = card
        card.set_selected(True)

    # ── 이미지 추가 ───────────────────────────────────────────
    def _pick_files(self):
        paths = filedialog.askopenfilenames(
            title="이미지 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
        for p in paths:
            self._add_image(p)
        if paths:
            self._refresh()

    def _on_drop(self, event):
        try:
            files = self.tk.splitlist(event.data)
        except Exception:
            files = event.data.strip().split()
        added = 0
        for f in files:
            f = f.strip("{}")
            if Path(f).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
                self._add_image(f)
                added += 1
        if added:
            self._refresh()

    def _add_keyword(self):
        kw = self._kw_entry.get().strip()
        if not kw:
            return
        self._queue.add(keyword=kw)
        self._kw_entry.delete(0, "end")
        self._refresh()

    def _add_image(self, path: str):
        self._queue.add(keyword=Path(path).stem, image_path=path)

    # ── 버튼 핸들러 ───────────────────────────────────────────
    def _on_delete(self):
        if self._selected_card:
            try:
                self._queue.remove(self._selected_card.item["id"])
            except Exception:
                pass
            self._refresh()

    def _on_settings(self):
        def on_save(cfg):
            self._config = cfg
            self._update_top_bar()
            self._refresh()
        SettingsWindow(self, self._config, on_save)

    def _on_learn(self):
        if not self._config.anthropic_api_key:
            messagebox.showwarning("설정 필요", "API 키를 먼저 입력하세요.")
            return self._on_settings()
        if self._running:
            return messagebox.showinfo("안내", "실행 중에는 학습할 수 없습니다.")
        # 학습도 마우스 위치를 읽으므로 접근성 불필요하지만 일관성 위해 체크
        # (learn.py는 pyautogui.position()만 사용하므로 실제로는 필요없음)
        self._running = True
        self._btn_run.configure(state="disabled")
        self._progress_label.configure(text="UI 학습 중...")
        def _run():
            try:
                from learn import start_learn
                start_learn()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("학습 오류", str(e)))
            def _learn_done():
                self._running = False
                self._btn_run.configure(state="normal")
            self.after(0, _learn_done)
            self.after(0, self._refresh)
        threading.Thread(target=_run, daemon=True).start()

    def _on_run(self):
        if not self._config.anthropic_api_key:
            messagebox.showwarning("설정 필요", "API 키를 먼저 입력하세요.")
            return self._on_settings()
        if not ACTIONS_FILE.exists():
            return messagebox.showwarning("학습 필요", "UI 학습을 먼저 하세요.")

        # 접근성 권한 체크 (실제 마우스 움직임 테스트)
        from suno_bot import check_accessibility
        if not check_accessibility():
            messagebox.showerror("접근성 권한 없음",
                "마우스를 제어할 수 없습니다!\n\n"
                "시스템 설정 → 개인정보 보호 및 보안 → 접근성\n"
                "→ '수노자동화' 앱을 추가하고 켜주세요.\n\n"
                "이미 있으면 삭제 후 다시 추가하세요.\n"
                "추가 후 앱을 재시작하세요.")
            subprocess.Popen(["open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
            return

        if self._running:
            return messagebox.showinfo("안내", "이미 실행 중입니다.")

        item = None
        if self._selected_card and self._selected_card.item["status"] in (STATUS_PENDING, STATUS_FAILED):
            item = self._selected_card.item
        if not item:
            pending = self._queue.get_pending()
            if not pending:
                return messagebox.showinfo("안내", "키워드 또는 이미지를 먼저 추가하세요.")
            item = pending[0]

        total = self._config.korean_songs + self._config.english_songs + self._config.instrumental_songs
        if total == 0:
            return messagebox.showwarning("설정 필요", "곡 수를 1 이상으로 설정하세요.")
        scope = {"songs": "곡 생성만", "videos": "곡+영상", "upload": "곡+영상+YouTube"}.get(self._config.pipeline_scope, "곡 생성만")
        if not messagebox.askokcancel("실행",
            f"키워드: {item['keyword']}\n총 {total}곡 | 범위: {scope}\n\n"
            f"Chrome에서 suno.com 로그인 필요.\n실행?"):
            return

        self._start_pipeline(item)

    def _start_pipeline(self, item):
        self._running = True
        self._stop_flag.clear()
        self._btn_run.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._queue.update_status(item["id"], STATUS_PROCESSING)
        self._refresh()

        def _progress(step, cur, total):
            pct = cur / total if total else 0
            self.after(0, lambda: self._progress_bar.set(pct))
            self.after(0, lambda: self._progress_label.configure(
                text=f"{int(pct * 100)}% — {step}"))

        def _run():
            from suno_bot import clear_log, get_log
            clear_log()
            try:
                from pipeline import Pipeline
                Pipeline(self._config).run(item, progress_callback=_progress, stop_event=self._stop_flag)
                self._queue.update_status(item["id"], STATUS_DONE)
                self.after(0, self._on_done)
            except Exception as e:
                tb = traceback.format_exc()
                self._queue.update_status(item["id"], STATUS_FAILED, error=str(e))
                self.after(0, lambda: self._on_error(str(e), tb))

        threading.Thread(target=_run, daemon=True).start()

    def _on_stop(self):
        self._stop_flag.set()
        self._btn_stop.configure(state="disabled")
        self._progress_label.configure(text="중단 중...")
        # 로그 보기 버튼 표시
        self.after(2000, self._show_log_button)

    def _show_log_button(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._progress_label.configure(text="중단됨 — 아래 '로그' 버튼으로 확인")
        self._refresh()

    def _on_done(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._progress_bar.set(1.0)
        self._progress_label.configure(text="100% — 완료!")
        self._refresh()

    def _on_error(self, msg, tb):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._progress_bar.set(0)
        self._progress_label.configure(text="오류 발생 — '로그' 버튼으로 확인")
        self._refresh()
        messagebox.showerror("오류", f"{msg}\n\n{tb[-500:]}")

    def _on_show_log(self):
        """실행 로그를 보여주고 복사할 수 있게 한다."""
        from suno_bot import get_log
        log_text = get_log() or "로그가 없습니다."

        win = ctk.CTkToplevel(self)
        win.title("실행 로그")
        win.geometry("600x400")
        win.grab_set()

        txt = ctk.CTkTextbox(win, font=("Menlo", 12))
        txt.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        txt.insert("1.0", log_text)
        txt.configure(state="disabled")

        def _copy():
            self.clipboard_clear()
            self.clipboard_append(log_text)
            messagebox.showinfo("복사됨", "로그가 클립보드에 복사되었습니다.", parent=win)

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn_row, text="로그 복사", height=36, fg_color=ACCENT,
                       command=_copy).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="닫기", height=36, fg_color="gray30",
                       command=win.destroy).pack(side="right", padx=4)


if __name__ == "__main__":
    App().mainloop()
