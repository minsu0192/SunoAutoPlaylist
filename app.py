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
# 큐 카드 (QueueCard)                                                  #
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

        self.bind("<Button-1>", self._click)

        # 상태 아이콘/텍스트
        status_frame = ctk.CTkFrame(self, fg_color="transparent", width=80)
        status_frame.pack(side="left", padx=(15, 5))

        self.status_label = ctk.CTkLabel(status_frame, text=status_text, font=("", 12, "bold"), text_color=color)
        self.status_label.pack(side="left")
        self.status_label.bind("<Button-1>", self._click)

        # 키워드
        self.kw_label = ctk.CTkLabel(self, text=item["keyword"], font=("", 14, "bold"), anchor="w")
        self.kw_label.pack(side="left", fill="x", expand=True, padx=10)
        self.kw_label.bind("<Button-1>", self._click)

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
        try:
            cfg = Config.load()
            # 키워드 폴더 (videos/upload scope)
            path = Path(cfg.output_dir) / self.item["keyword"]
            # completed 폴더 (songs scope)
            completed = Path.home() / "SunoOutput" / "completed"
            if path.exists():
                subprocess.Popen(["open", str(path)])
            elif completed.exists():
                subprocess.Popen(["open", str(completed)])
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
                                  ("assemble", " 빠른 조립", "🎬"),
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

        ver = ctk.CTkLabel(info_frame, text="v1.10.1", font=("", 10), text_color="gray50")
        ver.pack()

        # ── 메인 콘텐츠 영역 ──
        self.main_view = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_MAIN)
        self.main_view.grid(row=0, column=1, sticky="nsew")

        # 각 페이지용 프레임 초기화
        self.pages = {}
        self._build_generator_page()
        self._build_assemble_page()
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

        # 상단 입력 카드
        input_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=15)
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

        # ── 프로그래스 바 ──
        prog_frame = ctk.CTkFrame(page, fg_color="transparent", height=55)
        prog_frame.pack(fill="x", padx=20, pady=(0, 4))
        prog_frame.pack_propagate(False)

        self._progress_bar = ctk.CTkProgressBar(prog_frame, height=8, progress_color=ACCENT)
        self._progress_bar.pack(fill="x", pady=(4, 0))
        self._progress_bar.set(0)

        self._progress_label = ctk.CTkLabel(prog_frame, text="", font=("", 11), text_color="gray50", wraplength=500, justify="left")
        self._progress_label.pack(fill="x", pady=(2, 0))

        # ── 하단 실행/중단 버튼 ──
        btn_bar = ctk.CTkFrame(page, fg_color="transparent", height=56)
        btn_bar.pack(fill="x", padx=20, pady=(0, 15))
        btn_bar.pack_propagate(False)

        inner = ctk.CTkFrame(btn_bar, fg_color="transparent")
        inner.pack(expand=True)

        self._btn_run = ctk.CTkButton(inner, text="▶ 실행", width=120, height=40,
                                       font=("", 14, "bold"), fg_color=ACCENT,
                                       hover_color="#7C3AED", command=self._on_run)
        self._btn_run.pack(side="left", padx=6)

        self._btn_stop = ctk.CTkButton(inner, text="⏹ 중단", width=90, height=40,
                                        fg_color="#e74c3c", hover_color="#c0392b",
                                        command=self._on_stop, state="disabled")
        self._btn_stop.pack(side="left", padx=6)

    # ──────────────────────────────────────────────────────────
    # [페이지 1.5] 빠른 조립 (Assemble) — 기존 mp3 + 이미지로 영상 만들기
    # ──────────────────────────────────────────────────────────
    def _build_assemble_page(self):
        page = ctk.CTkScrollableFrame(self.main_view, fg_color="transparent")
        self.pages["assemble"] = page

        ctk.CTkLabel(page, text="🎬 빠른 조립",
                     font=("", 20, "bold")).pack(anchor="w", padx=30, pady=(30, 5))
        ctk.CTkLabel(page, text="이미 받아둔 mp3와 이미지로 영상을 즉시 조립합니다.",
                     font=("", 12), text_color="gray60").pack(anchor="w", padx=30, pady=(0, 20))

        # ── 영상 제목 ──
        title_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=12)
        title_card.pack(fill="x", padx=25, pady=(0, 10))
        ctk.CTkLabel(title_card, text="영상 제목 (폴더명/파일명)", font=("", 13, "bold"),
                     text_color="gray70").pack(anchor="w", padx=20, pady=(15, 5))
        self._asm_title = ctk.CTkEntry(title_card, height=42,
                                        placeholder_text="예: autumn_breeze_playlist",
                                        border_width=0, fg_color="gray14")
        self._asm_title.pack(fill="x", padx=20, pady=(0, 15))

        # ── 음원 파일들 ──
        mp3_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=12)
        mp3_card.pack(fill="x", padx=25, pady=10)

        mp3_header = ctk.CTkFrame(mp3_card, fg_color="transparent")
        mp3_header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(mp3_header, text="🎵 음원 파일 (순서대로)",
                     font=("", 13, "bold"), text_color="gray70").pack(side="left")
        ctk.CTkButton(mp3_header, text="+ 추가", width=80, height=28,
                      fg_color=ACCENT, hover_color="#7C3AED",
                      command=self._asm_pick_mp3s).pack(side="right")
        ctk.CTkButton(mp3_header, text="모두 삭제", width=80, height=28,
                      fg_color="gray25", hover_color="#e74c3c",
                      command=self._asm_clear_mp3s).pack(side="right", padx=5)

        self._asm_mp3_frame = ctk.CTkFrame(mp3_card, fg_color="gray14", corner_radius=8)
        self._asm_mp3_frame.pack(fill="x", padx=20, pady=(5, 15))
        self._asm_mp3_paths: list[Path] = []
        self._asm_mp3_label = ctk.CTkLabel(self._asm_mp3_frame, text="선택된 파일 없음",
                                            text_color="gray50", font=("", 11))
        self._asm_mp3_label.pack(pady=15)

        # ── 배경 이미지 ──
        img_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=12)
        img_card.pack(fill="x", padx=25, pady=10)

        img_header = ctk.CTkFrame(img_card, fg_color="transparent")
        img_header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(img_header, text="🖼 배경 이미지 (1장)",
                     font=("", 13, "bold"), text_color="gray70").pack(side="left")
        ctk.CTkButton(img_header, text="선택", width=80, height=28,
                      fg_color=ACCENT, hover_color="#7C3AED",
                      command=self._asm_pick_image).pack(side="right")

        self._asm_img_path: Path | None = None
        self._asm_img_label = ctk.CTkLabel(img_card, text="선택된 이미지 없음",
                                            text_color="gray50", font=("", 11))
        self._asm_img_label.pack(pady=(0, 15))

        # ── 옵션 ──
        opt_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=12)
        opt_card.pack(fill="x", padx=25, pady=10)
        ctk.CTkLabel(opt_card, text="⚙️ 옵션", font=("", 13, "bold"),
                     text_color="gray70").pack(anchor="w", padx=20, pady=(15, 10))

        # 실행 범위
        scope_row = ctk.CTkFrame(opt_card, fg_color="transparent")
        scope_row.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(scope_row, text="실행 범위", width=120,
                     anchor="w").pack(side="left")
        self._asm_scope = ctk.StringVar(value="video")
        ctk.CTkSegmentedButton(scope_row, values=["video", "upload"],
                                variable=self._asm_scope,
                                fg_color="gray20",
                                selected_color=ACCENT).pack(side="left")
        ctk.CTkLabel(scope_row, text="  video=영상만 / upload=영상+YouTube",
                     font=("", 10), text_color="gray50").pack(side="left", padx=10)

        # 썸네일 텍스트 (오버라이드 가능)
        thumb_row = ctk.CTkFrame(opt_card, fg_color="transparent")
        thumb_row.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(thumb_row, text="썸네일 문구", width=120,
                     anchor="w").pack(side="left")
        self._asm_thumb_text = ctk.CTkEntry(thumb_row, height=32,
                                             placeholder_text="비워두면 설정값 사용",
                                             border_width=0, fg_color="gray14")
        self._asm_thumb_text.pack(side="left", fill="x", expand=True)

        # 썸네일 사이즈
        size_row = ctk.CTkFrame(opt_card, fg_color="transparent")
        size_row.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(size_row, text="썸네일 크기", width=120,
                     anchor="w").pack(side="left")
        self._asm_thumb_size = ctk.StringVar(value="M")
        ctk.CTkSegmentedButton(size_row, values=["M", "XL"],
                                variable=self._asm_thumb_size,
                                fg_color="gray20",
                                selected_color=ACCENT).pack(side="left")

        # ── 진행 상황 ──
        prog_frame = ctk.CTkFrame(page, fg_color="transparent")
        prog_frame.pack(fill="x", padx=25, pady=(15, 5))
        self._asm_progress_bar = ctk.CTkProgressBar(prog_frame, height=8,
                                                     progress_color=ACCENT)
        self._asm_progress_bar.pack(fill="x")
        self._asm_progress_bar.set(0)
        self._asm_progress_label = ctk.CTkLabel(prog_frame, text="",
                                                 font=("", 11), text_color="gray50",
                                                 wraplength=600, justify="left")
        self._asm_progress_label.pack(pady=(5, 0))

        # ── 실행 버튼 ──
        ctk.CTkButton(page, text="▶ 조립 시작", height=50, fg_color=ACCENT,
                      hover_color="#7C3AED", font=("", 15, "bold"),
                      command=self._asm_run).pack(fill="x", padx=25, pady=(15, 30))

        # 드래그앤드롭 활성화
        self._asm_setup_dnd()

    def _asm_setup_dnd(self):
        """빠른 조립 페이지 DnD 설정"""
        try:
            from tkinterdnd2 import DND_FILES

            # mp3 영역
            self._asm_mp3_frame.drop_target_register(DND_FILES)
            self._asm_mp3_frame.dnd_bind("<<Drop>>", self._asm_on_drop_mp3)

            # 이미지 영역
            self._asm_img_label.drop_target_register(DND_FILES)
            self._asm_img_label.dnd_bind("<<Drop>>", self._asm_on_drop_image)

            # 안내 텍스트 업데이트
            for w in self._asm_mp3_frame.winfo_children():
                if isinstance(w, ctk.CTkLabel):
                    w.configure(text="📂 mp3 파일을 여기로 드래그하거나 '+ 추가' 클릭")
            self._asm_img_label.configure(text="🖼 이미지를 여기로 드래그하거나 '선택' 클릭")
        except Exception as e:
            pass  # tkinterdnd2 없으면 클릭으로만

    def _parse_dnd_files(self, data: str) -> list[str]:
        """DnD에서 받은 파일 경로 문자열 파싱 (공백/중괄호 처리)"""
        try:
            return list(self.tk.splitlist(data))
        except Exception:
            return data.strip().split()

    def _asm_on_drop_mp3(self, event):
        files = self._parse_dnd_files(event.data)
        added = 0
        for f in files:
            f = f.strip("{}")
            if Path(f).suffix.lower() == ".mp3":
                self._asm_mp3_paths.append(Path(f))
                added += 1
        if added:
            self._asm_refresh_mp3_list()

    def _asm_on_drop_image(self, event):
        files = self._parse_dnd_files(event.data)
        for f in files:
            f = f.strip("{}")
            if Path(f).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
                self._asm_img_path = Path(f)
                self._asm_img_label.configure(text=f"📷 {self._asm_img_path.name}",
                                              text_color="white")
                break

    def _asm_pick_mp3s(self):
        paths = filedialog.askopenfilenames(
            title="음원 파일 선택 (순서대로 선택)",
            filetypes=[("MP3", "*.mp3")],
        )
        for p in paths:
            self._asm_mp3_paths.append(Path(p))
        self._asm_refresh_mp3_list()

    def _asm_clear_mp3s(self):
        self._asm_mp3_paths = []
        self._asm_refresh_mp3_list()

    def _asm_refresh_mp3_list(self):
        # 기존 내용 지우기
        for w in self._asm_mp3_frame.winfo_children():
            w.destroy()

        if not self._asm_mp3_paths:
            ctk.CTkLabel(self._asm_mp3_frame,
                         text="📂 mp3 파일을 여기로 드래그하거나 '+ 추가' 클릭",
                         text_color="gray50", font=("", 11)).pack(pady=15)
        else:
            for i, p in enumerate(self._asm_mp3_paths):
                row = ctk.CTkFrame(self._asm_mp3_frame, fg_color="transparent")
                row.pack(fill="x", padx=10, pady=2)
                ctk.CTkLabel(row, text=f"{i+1:2d}.", width=30,
                             text_color="gray50").pack(side="left")
                ctk.CTkLabel(row, text=p.name, anchor="w",
                             text_color="white").pack(side="left", fill="x", expand=True)
                ctk.CTkButton(row, text="✕", width=24, height=24,
                              fg_color="transparent", hover_color="#e74c3c",
                              text_color="gray50",
                              command=lambda idx=i: self._asm_remove_mp3(idx)).pack(side="right")

        # DnD 재등록 (자식 위젯 변경 후에도 frame은 그대로지만 안전하게)
        try:
            from tkinterdnd2 import DND_FILES
            self._asm_mp3_frame.drop_target_register(DND_FILES)
            self._asm_mp3_frame.dnd_bind("<<Drop>>", self._asm_on_drop_mp3)
        except Exception:
            pass

    def _asm_remove_mp3(self, idx):
        if 0 <= idx < len(self._asm_mp3_paths):
            self._asm_mp3_paths.pop(idx)
            self._asm_refresh_mp3_list()

    def _asm_pick_image(self):
        path = filedialog.askopenfilename(
            title="배경 이미지 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.webp")],
        )
        if path:
            self._asm_img_path = Path(path)
            self._asm_img_label.configure(text=f"📷 {self._asm_img_path.name}",
                                          text_color="white")

    def _asm_run(self):
        # 검증
        title = self._asm_title.get().strip()
        if not title:
            messagebox.showwarning("입력 필요", "영상 제목을 입력하세요.")
            return
        if not self._asm_mp3_paths:
            messagebox.showwarning("입력 필요", "음원 파일을 1개 이상 선택하세요.")
            return
        if not self._asm_img_path or not self._asm_img_path.exists():
            messagebox.showwarning("입력 필요", "배경 이미지를 선택하세요.")
            return

        scope = self._asm_scope.get()
        thumb_text = self._asm_thumb_text.get().strip() or self._config.thumbnail_text or "Seoul Diary Playlist"
        thumb_size = self._asm_thumb_size.get()

        # 백그라운드 스레드에서 실행
        def _progress(msg, pct):
            self.after(0, lambda: self._asm_progress_bar.set(pct))
            self.after(0, lambda: self._asm_progress_label.configure(text=msg))

        def _run():
            try:
                self._asm_assemble(title, self._asm_mp3_paths,
                                   self._asm_img_path, scope,
                                   thumb_text, thumb_size, _progress)
            except Exception as e:
                tb = traceback.format_exc()
                self.after(0, lambda: messagebox.showerror("조립 실패", f"{e}\n\n{tb[-500:]}"))

        threading.Thread(target=_run, daemon=True).start()

    def _asm_assemble(self, title, mp3_paths, img_path, scope, thumb_text, thumb_size, progress):
        from media_proc import make_video, make_thumbnail, build_tracklist
        import time as _t

        cfg = self._config
        output_base = Path(cfg.output_dir) / self._safe_name(title)
        output_base.mkdir(parents=True, exist_ok=True)

        # [1] 썸네일 생성
        progress(f"[1/3] 썸네일 생성 중... ('{thumb_text}', {thumb_size})", 0.15)
        thumb_path = output_base / "thumbnail.jpg"
        make_thumbnail(img_path, thumb_text, thumb_path,
                       channel_name=thumb_text, size_preset=thumb_size)

        # [2] 영상 조립
        progress(f"[2/3] MP4 영상 조립 중... ({len(mp3_paths)}곡)", 0.35)
        output_mp4 = output_base / f"{self._safe_name(title)}.mp4"
        make_video(mp3_paths, thumb_path, output_mp4)
        size_mb = output_mp4.stat().st_size / 1024 / 1024
        progress(f"[2/3] 영상 완료: {output_mp4.name} ({size_mb:.1f} MB)", 0.6)

        if scope == "video":
            progress(f"✅ 완료: {output_mp4}", 1.0)
            self.after(0, lambda: subprocess.Popen(["open", str(output_base)]))
            return

        # [3] YouTube 업로드
        if not cfg.youtube_client_secrets:
            progress("⚠️ YouTube 미설정 → 영상만 생성", 1.0)
            return

        progress("[3/3] YouTube 업로드 중...", 0.7)
        from yt_upload import YouTubeUploader

        # 트랙리스트 (파일명을 제목으로 사용)
        tracks = [(p, p.stem) for p in mp3_paths]
        tracklist = build_tracklist(tracks)

        # YouTube 메타데이터
        from lyrics_gen import generate_youtube_info
        try:
            yt_info = generate_youtube_info(title, len(mp3_paths), cfg.anthropic_api_key)
        except Exception:
            yt_info = {"title": title, "description": title, "tags": [title]}

        description = yt_info["description"]
        if tracklist:
            description = f"{description}\n\n📌 Tracklist\n{tracklist}"

        # 사진작가 크레딧 (있으면)
        from lyrics_gen import read_image_credit
        credit = read_image_credit(img_path)
        if credit:
            description = f"{description}\n\n{credit}"

        uploader = YouTubeUploader()
        url = uploader.upload(
            video_path=output_mp4, title=yt_info["title"],
            description=description, tags=yt_info["tags"],
            playlist_id=cfg.youtube_playlist_id or "",
            privacy=cfg.youtube_privacy,
        )
        progress(f"✅ 업로드 완료: {url}", 1.0)
        self.after(0, lambda: subprocess.Popen(["open", url]))

    @staticmethod
    def _safe_name(text: str) -> str:
        return "".join(c if c.isalnum() or c in " _-가-힣" else "_" for c in text).strip()[:50] or "untitled"

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
        self._add_setting_row(sec_api, "Unsplash Access Key", "unsplash_access_key", placeholder="시네마틱 이미지 (1순위, 권장)")
        self._add_setting_row(sec_api, "Pixabay API Key", "pixabay_api_key", placeholder="이미지 자동 검색용 (2순위 fallback)")

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

        # ── 썸네일 설정 ──
        sec_thumb = add_section("🖼 썸네일 텍스트")
        sec_thumb.pack(fill="x", padx=25)

        self._add_setting_row(sec_thumb, "썸네일 문구", "thumbnail_text", placeholder="Seoul Diary Playlist")
        self._add_setting_segmented(sec_thumb, "글씨 크기", "thumbnail_size", ["M", "XL"])

        # 글씨 크기 예시 안내
        hint = ctk.CTkLabel(
            sec_thumb,
            text="  M (작게) — 긴 문구 (예: Seoul Diary Playlist)\n  XL (크게) — 짧은 단어 (예: essential / playlist)",
            font=("", 11),
            text_color="gray60",
            justify="left",
        )
        hint.pack(anchor="w", padx=25, pady=(0, 10))

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
            self._progress_bar.set(0)
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
        paths = filedialog.askopenfilenames(filetypes=[("이미지", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
        for p in paths:
            self._queue.add(keyword=Path(p).stem, image_path=p)
        if paths: self._refresh_queue()

    def _on_drop(self, event):
        try: files = self.tk.splitlist(event.data)
        except Exception: files = event.data.strip().split()
        added = 0
        for f in files:
            f = f.strip("{}")
            if Path(f).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
                self._queue.add(keyword=Path(f).stem, image_path=f)
                added += 1
        if added: self._refresh_queue()

    def _save_settings(self):
        try:
            for k, v in self._vars.items():
                setattr(self._config, k, v.get())
            self._config.save()
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
            messagebox.showwarning("설정 필요", "API 키를 먼저 입력하세요.")
            return self._show_page("settings")
        if self._running:
            return messagebox.showinfo("안내", "실행 중에는 학습할 수 없습니다.")
        self._running = True
        self._btn_run.configure(state="disabled")
        self._progress_label.configure(text="시스템 학습 중 (마우스를 움직이지 마세요)...")
        def _run():
            try:
                from learn import start_learn
                start_learn()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("학습 오류", str(e)))
            def _learn_done():
                self._running = False
                self._btn_run.configure(state="normal")
                self._progress_label.configure(text="학습 완료!")
            self.after(0, _learn_done)
            self.after(0, self._refresh_queue)
        threading.Thread(target=_run, daemon=True).start()

    def _on_run(self):
        if not self._config.anthropic_api_key:
            messagebox.showwarning("설정 필요", "API 키를 먼저 입력하세요.")
            return self._show_page("settings")
        if not ACTIONS_FILE.exists():
            return messagebox.showwarning("학습 필요", "UI 학습을 먼저 진행해주세요.")

        # 접근성 권한 체크
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
            if not pending: return messagebox.showinfo("안내", "대기 중인 작업이 없습니다.")
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
        self._pipeline_step = ""  # 현재 파이프라인 단계
        self._btn_run.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._queue.update_status(item["id"], STATUS_PROCESSING)
        self._refresh_queue()
        self._start_live_log()  # 실시간 로그 표시 시작

        def _progress(step, cur, total):
            pct = cur / total if total else 0
            self._pipeline_step = f"[{int(pct*100)}%] {step}"
            self.after(0, lambda: self._progress_bar.set(pct))

        def _run():
            from suno_bot import clear_log
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

    def _start_live_log(self):
        """실행 중 2초마다 최신 로그를 프로그레스 라벨에 표시"""
        if not self._running:
            return
        try:
            from suno_bot import get_log
            log = get_log()
            if log:
                last_line = log.strip().split("\n")[-1]
                display = f"{self._pipeline_step}\n{last_line}"
            else:
                display = self._pipeline_step
            self._progress_label.configure(text=display)
        except Exception:
            pass
        self.after(2000, self._start_live_log)

    def _on_stop(self):
        self._stop_flag.set()
        self._btn_stop.configure(state="disabled")
        self._progress_label.configure(text="중지 요청 중...")
        self.after(2000, self._show_stop_done)

    def _show_stop_done(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._progress_label.configure(text="중단됨 — [실행 로그]에서 확인")
        self._refresh_queue()

    def _on_done(self):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._progress_bar.set(1.0)
        self._progress_label.configure(text="100% — 완료!")
        self._refresh_queue()
        self._refresh_logs()

    def _on_error(self, msg, tb):
        self._running = False
        self._btn_run.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._progress_bar.set(0)
        self._progress_label.configure(text="오류 발생 — [실행 로그]에서 확인")
        self._refresh_queue()
        self._refresh_logs()
        messagebox.showerror("오류", f"{msg}\n\n{tb[-500:]}")

    def _show_onboarding(self):
        messagebox.showinfo("Suno Dash", "환영합니다! 먼저 [설정 관리]에서 API 키를 입력해주세요.")
        self._show_page("settings")

    def _check_accessibility_silent(self):
        try:
            from suno_bot import check_accessibility
            if not check_accessibility():
                messagebox.showwarning("접근성 권한 필요",
                    "시스템 설정 → 개인정보 보호 → 접근성\n→ 수노자동화 추가 후 켜주세요")
                subprocess.Popen(["open",
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
        except Exception:
            pass


if __name__ == "__main__":
    App().mainloop()
