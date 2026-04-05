"""
app.py — 수노자동화 메인 GUI (Modern Dashboard Version)
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

# 디자인 상수
ACCENT = "#8B5CF6"  # 보라색 액센트
BG_SIDEBAR = "#1A1A1A"
BG_MAIN = "#121212"
CARD_BG = "#1E1E1E"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACTIONS_FILE = Path.home() / ".suno_actions.json"

# ================================================================== #
# Cmd+V 패치 (macOS 사용자 편의성)                                      #
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
# 큐 카드 (QueueCard) - 디자인 개선                                     #
# ================================================================== #

class QueueCard(ctk.CTkFrame):
    STATUS_MAP = {
        STATUS_PENDING: ("gray60", "⏳ 대기"),
        STATUS_PROCESSING: (ACCENT, "⚙️ 진행중"),
        STATUS_DONE: ("#2ecc71", "✅ 완료"),
        STATUS_FAILED: ("#e74c3c", "❌ 실패"),
    }

    def __init__(self, parent, item: dict, on_select=None, on_delete=None):
        color, status_text = self.STATUS_MAP.get(item["status"], ("gray50", "❓ 알수없음"))
        super().__init__(parent, corner_radius=12, fg_color=CARD_BG, height=60)
        self.pack_propagate(False)
        self.item = item
        self._on_select = on_select
        self._on_delete = on_delete

        # 전체 카드 클릭 이벤트
        for widget in [self]:
             widget.bind("<Button-1>", self._click)

        # 상태 아이콘/텍스트
        status_frame = ctk.CTkFrame(self, fg_color="transparent", width=80)
        status_frame.pack(side="left", padx=(15, 5))
        
        self.status_label = ctk.CTkLabel(status_frame, text=status_text, font=("", 12, "bold"), text_color=color)
        self.status_label.pack(side="left")

        # 키워드
        self.kw_label = ctk.CTkLabel(self, text=item["keyword"], font=("", 14, "bold"), anchor="w")
        self.kw_label.pack(side="left", fill="x", expand=True, padx=10)

        # 작업 버튼 프레임
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(side="right", padx=10)

        if item["status"] == STATUS_DONE:
            ctk.CTkButton(self.btn_frame, text="📂", width=32, height=32, fg_color="gray25", hover_color="gray35",
                           command=self._open_folder).pack(side="left", padx=2)
        
        ctk.CTkButton(self.btn_frame, text="🗑", width=32, height=32, fg_color="transparent", 
                       hover_color="#e74c3c", text_color="gray60",
                       command=self._delete).pack(side="left", padx=2)

    def _click(self, _=None):
        if self._on_select:
            self._on_select(self)

    def _delete(self):
        if self._on_delete:
            self._on_delete(self.item["id"])

    def _open_folder(self):
        # 결과 폴더 열기 (output_dir/{keyword})
        try:
            cfg = Config.load()
            path = Path(cfg.output_dir) / self.item["keyword"]
            if path.exists():
                subprocess.Popen(["open", str(path)])
            else:
                messagebox.showinfo("안내", "폴더를 찾을 수 없습니다.")
        except Exception:
            pass

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
        self._active_page = "generator"

        self.title("SunoAuto DASH")
        self.geometry("850x700")
        self.minsize(800, 600)

        _patch_paste(self)
        self._build_layout()
        self._show_page("generator")
        self._refresh_queue()

        if not self._config.anthropic_api_key:
            self.after(500, self._show_onboarding)
        else:
            self.after(1000, self._check_accessibility_silent)

    def _build_layout(self):
        """좌측 사이드바 + 우측 메인 영역 레이아웃 설정"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── 사이드바 ──
        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0, fg_color=BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        logo = ctk.CTkLabel(self.sidebar, text="SUNO DASH", font=("", 18, "bold"), text_color=ACCENT)
        logo.pack(pady=(30, 40))

        self.nav_btns = {}
        for name, label, icon in [("generator", " 작업 생성", "🎵"), 
                                  ("settings", " 설정 관리", "⚙️"), 
                                  ("logs", " 실행 로그", "📜")]:
            btn = ctk.CTkButton(self.sidebar, text=f"{icon}{label}", 
                                 height=45, anchor="w", corner_radius=8,
                                 fg_color="transparent", text_color="gray70",
                                 hover_color="gray25",
                                 command=lambda n=name: self._show_page(n))
            btn.pack(fill="x", padx=10, pady=4)
            self.nav_btns[name] = btn

        # 하단 정보
        info_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        info_frame.pack(side="bottom", fill="x", pady=20, padx=10)
        
        self.learn_btn = ctk.CTkButton(info_frame, text="UI 학습하기", height=32, 
                                        fg_color="gray25", hover_color=ACCENT,
                                        command=self._on_learn)
        self.learn_btn.pack(fill="x", pady=5)
        
        ver = ctk.CTkLabel(info_frame, text="v1.0.0", font=("", 10), text_color="gray50")
        ver.pack()

        # ── 메인 콘텐츠 영역 ──
        self.main_view = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_MAIN)
        self.main_view.grid(row=0, column=1, sticky="nsew")
        
        # 각 페이지용 프레임 초기화
        self.pages = {}
        self._build_generator_page()
        self._build_settings_page()
        self._build_logs_page()

    def _show_page(self, name):
        self._active_page = name
        for p_name, p_frame in self.pages.items():
            if p_name == name:
                p_frame.pack(fill="both", expand=True)
                self.nav_btns[p_name].configure(fg_color=ACCENT, text_color="white")
            else:
                p_frame.pack_forget()
                self.nav_btns[p_name].configure(fg_color="transparent", text_color="gray70")

    # ──────────────────────────────────────────────────────────
    # [페이지 1] 작업 생성 (Generator)
    # ──────────────────────────────────────────────────────────
    def _build_generator_page(self):
        page = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.pages["generator"] = page

        bg_set = BG_THEMES.get(self._config.bg_style, BG_THEMES["Zinc"])
        card_bg = bg_set["card"]

        # 상단 입력 카드
        input_card = ctk.CTkFrame(page, fg_color=card_bg, corner_radius=15)
        input_card.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(input_card, text="새 작업 추가", font=("", 14, "bold"), text_color="gray70").pack(anchor="w", padx=20, pady=(15, 5))

        kw_row = ctk.CTkFrame(input_card, fg_color="transparent")
        kw_row.pack(fill="x", padx=20, pady=(0, 10))
        
        self._kw_entry = ctk.CTkEntry(kw_row, height=45, placeholder_text="키워드를 입력하세요 (예: 새벽 감성 lofi)", border_width=0, fg_color="gray14")
        self._kw_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._kw_entry.bind("<Return>", lambda _: self._add_keyword())

        ctk.CTkButton(kw_row, text="추가하기", width=100, height=45, fg_color=ACCENT, hover_color="#7C3AED", font=("", 13, "bold"),
                       command=self._add_keyword).pack(side="right")

        # 드롭 영역 (이미지)
        self._drop_frame = ctk.CTkFrame(input_card, fg_color="gray14", height=60, corner_radius=10, border_width=1, border_color="gray25")
        self._drop_frame.pack(fill="x", padx=20, pady=(0, 20))
        self._drop_frame.pack_propagate(False)
        self._drop_frame.bind("<Button-1>", lambda _: self._pick_files())

        self._drop_label = ctk.CTkLabel(self._drop_frame, text="📸 배경 이미지 추가 (선택사항, 파일명=키워드)", font=("", 12), text_color="gray50")
        self._drop_label.pack(expand=True)
        self._drop_label.bind("<Button-1>", lambda _: self._pick_files())
        self._setup_dnd()

        # 큐 목록 영역
        list_header = ctk.CTkFrame(page, fg_color="transparent")
        list_header.pack(fill="x", padx=25, pady=(10, 0))
        ctk.CTkLabel(list_header, text="작업 대기열", font=("", 13, "bold"), text_color="gray50").pack(side="left")
        self._count_label = ctk.CTkLabel(list_header, text="0 Tasks", font=("", 11), text_color="gray40")
        self._count_label.pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=20, pady=5)

    # ──────────────────────────────────────────────────────────
    # [페이지 2] 설정 (Settings)
    # ──────────────────────────────────────────────────────────
    def _build_settings_page(self):
        page = ctk.CTkScrollableFrame(self.main_view, fg_color="transparent")
        self.pages["settings"] = page

        ctk.CTkLabel(page, text="애플리케이션 설정", font=("", 20, "bold")).pack(anchor="w", padx=30, pady=(30, 20))

        self._vars = {}
        
        # 섹션 도우미
        def add_section(title):
            ctk.CTkLabel(page, text=title, font=("", 14, "bold"), text_color=ACCENT).pack(anchor="w", padx=30, pady=(20, 10))
            return ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=12)

        # ── API 설정 ──
        sec_api = add_section("🔑 API 키 설정")
        sec_api.pack(fill="x", padx=25)
        
        self._add_setting_row(sec_api, "Anthropic API Key", "anthropic_api_key", placeholder="sk-ant-...")
        self._add_setting_row(sec_api, "Pixabay API Key", "pixabay_api_key", placeholder="이미지 자동 검색용 (선택)")

        # ── 곡 생성 설정 ──
        sec_song = add_section("🎵 생성 옵션")
        sec_song.pack(fill="x", padx=25)
        
        song_count_row = ctk.CTkFrame(sec_song, fg_color="transparent")
        song_count_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(song_count_row, text="곡 수 (KR / EN / Inst)").pack(side="left")
        
        for key in ["korean_songs", "english_songs", "instrumental_songs"]:
            v = ctk.IntVar(value=getattr(self._config, key))
            self._vars[key] = v
            ctk.CTkEntry(song_count_row, textvariable=v, width=50).pack(side="right", padx=5)

        self._add_setting_segmented(sec_song, "보컬 선택 (2곡 중)", "vocal_pick", ["longer", "shorter", "random", "both"])
        self._add_setting_segmented(sec_song, "실행 범위", "pipeline_scope", ["songs", "videos", "upload"])

        # ── YouTube ──
        sec_yt = add_section("📺 YouTube 설정")
        sec_yt.pack(fill="x", padx=25)
        
        yt_row = ctk.CTkFrame(sec_yt, fg_color="transparent")
        yt_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(yt_row, text="Client Secrets").pack(side="left")
        v_yt = ctk.StringVar(value=self._config.youtube_client_secrets)
        self._vars["youtube_client_secrets"] = v_yt
        ctk.CTkEntry(yt_row, textvariable=v_yt, width=250).pack(side="right", padx=(5, 0))
        ctk.CTkButton(yt_row, text="...", width=30, command=self._pick_secrets).pack(side="right", padx=5)

        self._add_setting_row(sec_yt, "Playlist ID", "youtube_playlist_id")
        self._add_setting_segmented(sec_yt, "공개 상태", "youtube_privacy", ["public", "unlisted", "private"])
        
        ctk.CTkButton(sec_yt, text="Google 계정 인증하기", fg_color="#e74c3c", hover_color="#c0392b", command=self._google_auth).pack(fill="x", padx=20, pady=10)

        # ── 경로 ──
        sec_path = add_section("📂 저장 경로")
        sec_path.pack(fill="x", padx=25)
        
        path_row = ctk.CTkFrame(sec_path, fg_color="transparent")
        path_row.pack(fill="x", padx=20, pady=10)
        v_out = ctk.StringVar(value=self._config.output_dir)
        self._vars["output_dir"] = v_out
        ctk.CTkEntry(path_row, textvariable=v_out).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(path_row, text="폴더 선택", width=80, command=lambda: v_out.set(filedialog.askdirectory() or v_out.get())).pack(side="right", padx=5)

        # 저장 버튼
        ctk.CTkButton(page, text="설정 저장하기", height=50, fg_color=ACCENT, font=("", 15, "bold"), command=self._save_settings).pack(fill="x", padx=25, pady=40)

    def _add_setting_row(self, parent, label, var_key, placeholder=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text=label).pack(side="left")
        v = ctk.StringVar(value=getattr(self._config, var_key))
        self._vars[var_key] = v
        ctk.CTkEntry(row, textvariable=v, width=300, placeholder_text=placeholder, border_width=1).pack(side="right")

    def _add_setting_segmented(self, parent, label, var_key, values):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text=label).pack(side="left")
        v = ctk.StringVar(value=getattr(self._config, var_key))
        self._vars[var_key] = v
        ctk.CTkSegmentedButton(row, values=values, variable=v).pack(side="right")

    # ──────────────────────────────────────────────────────────
    # [페이지 3] 로그 (Logs)
    # ──────────────────────────────────────────────────────────
    def _build_logs_page(self):
        page = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.pages["logs"] = page

        ctk.CTkLabel(page, text="시스템 로그", font=("", 20, "bold")).pack(anchor="w", padx=30, pady=(30, 10))
        
        log_frame = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=12)
        log_frame.pack(fill="both", expand=True, padx=25, pady=(0, 20))

        self.log_text = ctk.CTkTextbox(log_frame, font=("Menlo", 12), fg_color="transparent", border_width=0)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        btn_row = ctk.CTkFrame(page, fg_color="transparent")
        btn_row.pack(fill="x", padx=25, pady=(0, 20))
        
        ctk.CTkButton(btn_row, text="로그 새로고침", width=120, fg_color="gray25", command=self._refresh_logs).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="로그 복사하기", width=120, fg_color=ACCENT, command=self._copy_logs).pack(side="left", padx=5)

    def _refresh_logs(self):
        from suno_bot import get_log
        content = get_log() or "기록된 로그가 없습니다."
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", content)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _copy_logs(self):
        content = self.log_text.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("완료", "로그가 클립보드에 복사되었습니다.")

    # ──────────────────────────────────────────────────────────
    # 공통 로직 (DND, Queue, Handlers)
    # ──────────────────────────────────────────────────────────
    def _setup_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES
            for w in (self._drop_frame, self._drop_label):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
            self._drop_label.configure(text="📸 이미지 드래그 또는 클릭 (파일명=키워드)")
        except Exception:
            self._drop_label.configure(text="📸 클릭하여 이미지 추가 (파일명=키워드)")

    def _refresh_queue(self):
        for c in self._cards:
            c.destroy()
        self._cards.clear()
        self._selected_card = None
        items = self._queue.get_all()
        self._count_label.configure(text=f"{len(items)} Tasks")
        for item in items:
            card = QueueCard(self._scroll, item, on_select=self._select_card, on_delete=self._delete_item)
            card.pack(fill="x", pady=4, padx=5)
            self._cards.append(card)
        
        if not self._running:
            pending = len(self._queue.get_pending())
            self._progress_label.configure(text=f"{pending}개 작업 대기 중" if pending else "새로운 키워드를 추가하세요")

    def _select_card(self, card: QueueCard):
        if self._selected_card:
            self._selected_card.set_selected(False)
        self._selected_card = card
        card.set_selected(True)

    def _delete_item(self, item_id):
        self._queue.remove(item_id)
        self._refresh_queue()

    def _add_keyword(self):
        kw = self._kw_entry.get().strip()
        if not kw: return
        self._queue.add(keyword=kw)
        self._kw_entry.delete(0, "end")
        self._refresh_queue()

    def _pick_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        for p in paths:
            self._queue.add(keyword=Path(p).stem, image_path=p)
        if paths: self._refresh_queue()

    def _on_drop(self, event):
        try: files = self.tk.splitlist(event.data)
        except Exception: files = event.data.strip().split()
        added = 0
        for f in files:
            f = f.strip("{}")
            if Path(f).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                self._queue.add(keyword=Path(f).stem, image_path=f)
                added += 1
        if added: self._refresh_queue()

    def _save_settings(self):
        try:
            for k, v in self._vars.items():
                setattr(self._config, k, v.get())
            self._config.save()
            self._update_theme_ui()  # 저장 후 즉시 테마 색상 반영
            messagebox.showinfo("성공", "설정이 저장되었습니다.")
            self._show_page("generator")
            self._refresh_queue()
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _pick_secrets(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p: self._vars["youtube_client_secrets"].set(p)

    def _google_auth(self):
        path = self._vars["youtube_client_secrets"].get().strip()
        if not path:
            messagebox.showwarning("경고", "client_secrets.json을 먼저 선택하세요.")
            return
        try:
            from yt_upload import YouTubeUploader
            YouTubeUploader().authenticate(path)
            messagebox.showinfo("성공", "Google 인증 완료!")
        except Exception as e:
            messagebox.showerror("실패", str(e))

    def _on_learn(self):
        if not self._config.anthropic_api_key:
            return self._show_page("settings")
        if self._running: return
        self._running = True
        self._btn_run.configure(state="disabled")
        self._progress_label.configure(text="시스템 학습 중 (마우스를 움직이지 마세요)...")
        def _run():
            try:
                from learn import start_learn
                start_learn()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("학습 오류", str(e)))
            self.after(0, self._on_done)
        threading.Thread(target=_run, daemon=True).start()

    def _on_run(self):
        if not self._config.anthropic_api_key:
            return self._show_page("settings")
        if not ACTIONS_FILE.exists():
            return messagebox.showwarning("학습 필요", "UI 학습을 먼저 진행해주세요.")

        item = None
        if self._selected_card and self._selected_card.item["status"] in (STATUS_PENDING, STATUS_FAILED):
            item = self._selected_card.item
        if not item:
            pending = self._queue.get_pending()
            if not pending: return messagebox.showinfo("안내", "대기 중인 작업이 없습니다.")
            item = pending[0]

        self._start_pipeline(item)

    def _start_pipeline(self, item):
        self._running = True
        self._stop_flag.clear()
        self._btn_run.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._queue.update_status(item["id"], STATUS_PROCESSING)
        self._refresh_queue()

        def _progress(step, cur, total):
            pct = cur / total if total else 0
            self.after(0, lambda: self._progress_bar.set(pct))
            self.after(0, lambda: self._progress_label.configure(text=f"[{int(pct*100)}%] {step}"))

        def _run():
            try:
                from pipeline import Pipeline
                Pipeline(self._config).run(item, progress_callback=_progress, stop_event=self._stop_flag)
                self._queue.update_status(item["id"], STATUS_DONE)
            except Exception as e:
                self._queue.update_status(item["id"], STATUS_FAILED, error=str(e))
            self.after(0, self._on_done)

        threading.Thread(target=_run, daemon=True).start()

    def _on_stop(self):
        self._stop_flag.set()
        self._btn_stop.configure(state="disabled")
        self._progress_label.configure(text="중지 요청 중...")

    def _on_done(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._progress_bar.set(0)
        self._refresh_queue()
        self._refresh_logs()

    def _show_onboarding(self):
        messagebox.showinfo("Suno Dash", "환영합니다! 먼저 [설정 관리]에서 API 키를 입력해주세요.")
        self._show_page("settings")

    def _check_accessibility_silent(self):
        try:
            from suno_bot import check_accessibility
            if not check_accessibility():
                messagebox.showwarning("접근성 권한 필요", "마우스 제어를 위해 시스템 설정에서 접근성 권한을 허용해주세요.")
        except Exception: pass

if __name__ == "__main__":
    App().mainloop()
   def _run():
            try:
                from pipeline import Pipeline
                Pipeline(self._config).run(item, progress_callback=_progress, stop_event=self._stop_flag)
                self._queue.update_status(item["id"], STATUS_DONE)
            except Exception as e:
                self._queue.update_status(item["id"], STATUS_FAILED, error=str(e))
            self.after(0, self._on_done)

        threading.Thread(target=_run, daemon=True).start()

    def _on_stop(self):
        self._stop_flag.set()
        self._btn_stop.configure(state="disabled")
        self._progress_label.configure(text="중지 요청 중...")

    def _on_done(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._progress_bar.set(0)
        self._refresh_queue()
        self._refresh_logs()

    def _show_onboarding(self):
        messagebox.showinfo("Suno Dash", "환영합니다! 먼저 [설정 관리]에서 API 키를 입력해주세요.")
        self._show_page("settings")

    def _check_accessibility_silent(self):
        try:
            from suno_bot import check_accessibility
            if not check_accessibility():
                messagebox.showwarning("접근성 권한 필요", "마우스 제어를 위해 시스템 설정에서 접근성 권한을 허용해주세요.")
        except Exception: pass

if __name__ == "__main__":
    App().mainloop()
lag)
                self._queue.update_status(item["id"], STATUS_DONE)
            except Exception as e:
                self._queue.update_status(item["id"], STATUS_FAILED, error=str(e))
            self.after(0, self._on_done)

        threading.Thread(target=_run, daemon=True).start()

    def _on_stop(self):
        self._stop_flag.set()
        self._btn_stop.configure(state="disabled")
        self._progress_label.configure(text="중지 요청 중...")

    def _on_done(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._progress_bar.set(0)
        self._refresh_queue()
        self._refresh_logs()

    def _show_onboarding(self):
        messagebox.showinfo("Suno Dash", "환영합니다! 먼저 [설정 관리]에서 API 키를 입력해주세요.")
        self._show_page("settings")

    def _check_accessibility_silent(self):
        try:
            from suno_bot import check_accessibility
            if not check_accessibility():
                messagebox.showwarning("접근성 권한 필요", "마우스 제어를 위해 시스템 설정에서 접근성 권한을 허용해주세요.")
        except Exception: pass

if __name__ == "__main__":
    App().mainloop()
mainloop()
 self._refresh_queue()
        self._refresh_logs()

    def _show_onboarding(self):
        messagebox.showinfo("Suno Dash", "환영합니다! 먼저 [설정 관리]에서 API 키를 입력해주세요.")
        self._show_page("settings")

    def _check_accessibility_silent(self):
        try:
            from suno_bot import check_accessibility
            if not check_accessibility():
                messagebox.showwarning("접근성 권한 필요", "마우스 제어를 위해 시스템 설정에서 접근성 권한을 허용해주세요.")
        except Exception: pass

if __name__ == "__main__":
    App().mainloop()
�요.")
        except Exception: pass

if __name__ == "__main__":
    App().mainloop()
