"""
수노 자동화 — macOS 메뉴바 앱
rumps 기반. Dock에 나타나지 않고 상단 메뉴바에만 🎵 아이콘으로 표시.

기능:
  - 큐 관리: ~/SunoProjects/input/ 폴더 감시, 대기 항목 수 표시
  - 예약 실행: 매분 체크, 설정 시간에 자동 실행
  - 지금 실행: 큐에서 첫 번째 대기 항목 즉시 처리
  - 설정 창: tkinter 설정 창 (subprocess)
  - 로그 보기: ~/.suno_auto.log 최근 50줄

실행: python suno_menu_bar.py
빌드: bash build_app.sh
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import rumps

from suno_project_manager import ProjectManager

CONFIG_FILE = Path.home() / ".suno_config.json"
LOG_FILE    = Path.home() / ".suno_auto.log"
SCRIPT_DIR  = Path(__file__).parent


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _get_pm(config: dict) -> ProjectManager:
    root = Path(config.get("projects_root", "~/SunoProjects")).expanduser()
    return ProjectManager(root)


def _append_log(text: str):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{ts}] {text}\n")


def _read_log_tail(n: int = 50) -> str:
    if not LOG_FILE.exists():
        return "로그가 없습니다."
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:]) or "로그가 비어 있습니다."


def _osascript(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True)
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# 메인 앱
# ---------------------------------------------------------------------------

class SunoMenuBar(rumps.App):

    def __init__(self):
        super().__init__("🎵", quit_button=None)
        self._proc    = None   # 실행 중인 pipeline subprocess
        self._log_fd  = None   # 로그 파일 핸들

        # 동적 타이틀 메뉴 아이템
        self.run_item      = rumps.MenuItem("▶ 지금 실행  (스캔 중...)", callback=self.run_now)
        self.schedule_item = rumps.MenuItem("⏰ 예약: 없음",  callback=None)
        self.status_item   = rumps.MenuItem("● 준비됨",       callback=None)

        self.queue_item  = rumps.MenuItem("⏳ 대기: 0개", callback=None)

        self.menu = [
            self.run_item,
            self.schedule_item,
            self.queue_item,
            None,
            rumps.MenuItem("📂 입력 폴더 열기",    callback=self.open_input),
            rumps.MenuItem("📁 결과물 폴더 열기",   callback=self.open_output),
            rumps.MenuItem("📋 로그 보기",          callback=self.show_log),
            None,
            rumps.MenuItem("🔄 UI 재학습",          callback=self.relearn),
            rumps.MenuItem("⚙️ 설정...",            callback=self.open_settings),
            rumps.MenuItem("❓ 사용 방법",           callback=self.show_help),
            None,
            self.status_item,
            None,
            rumps.MenuItem("종료", callback=rumps.quit_application),
        ]

        # 60초마다: 예약 체크 + 큐 갱신 + 완료 체크
        self._tick_timer = rumps.Timer(self._tick, 60)
        self._tick_timer.start()

        # 시작 시 즉시 스캔
        self._refresh_menu()
        self._check_first_run()

    # ------------------------------------------------------------------
    # 주기 작업
    # ------------------------------------------------------------------

    def _tick(self, _):
        self._refresh_menu()
        self._check_schedule()
        self._check_proc_done()

    def _refresh_menu(self):
        try:
            config = load_config()
            pm = _get_pm(config)
            pm.scan_input()
            stats = pm.get_stats()
            pending  = stats.get("pending", 0)
            done     = stats.get("done", 0)
            failed   = stats.get("failed", 0)
            total    = sum(stats.values())

            self.run_item.title = (
                f"▶ 지금 실행  ({pending}개 대기 중)"
                if pending else "▶ 지금 실행  (대기 없음)"
            )
            schedule_on = config.get("schedule_enabled", False)
            schedule    = config.get("schedule_time", "")
            if schedule_on and schedule:
                days = config.get("schedule_days", [])
                day_str = "".join(
                    lbl for k, lbl in
                    [("mon","월"),("tue","화"),("wed","수"),("thu","목"),
                     ("fri","금"),("sat","토"),("sun","일")]
                    if k in days
                )
                self.schedule_item.title = f"⏰ 예약: {schedule}  [{day_str}]"
            else:
                self.schedule_item.title = "⏰ 예약: 비활성"

            done_str   = f"  완료 {done}개" if done else ""
            failed_str = f"  실패 {failed}개" if failed else ""
            self.queue_item.title = (
                f"📊 전체 {total}개{done_str}{failed_str}"
                if total else "📊 프로젝트 없음"
            )
        except Exception:
            pass

    def _check_schedule(self):
        if self._proc and self._proc.poll() is None:
            return
        config = load_config()
        schedule = config.get("schedule_time", "").strip()
        if not schedule:
            return
        now = datetime.now().strftime("%H:%M")
        if now == schedule:
            _append_log(f"예약 실행 시작 ({schedule})")
            self._start_next_project(config)

    def _check_proc_done(self):
        if not self._proc:
            return
        ret = self._proc.poll()
        if ret is None:
            return
        if self._log_fd:
            self._log_fd.close()
            self._log_fd = None
        if ret == 0:
            self.status_item.title = "● 완료"
            _append_log("파이프라인 완료")
            rumps.notification("🎵 수노 완료", "성공", "로그 보기에서 결과를 확인하세요.")
        else:
            self.status_item.title = "● 오류 발생"
            _append_log(f"파이프라인 오류 (코드 {ret})")
            rumps.notification("🎵 수노 오류", f"종료 코드 {ret}", "로그 보기에서 오류를 확인하세요.")
        self._proc = None
        self._refresh_menu()

    # ------------------------------------------------------------------
    # 실행
    # ------------------------------------------------------------------

    @rumps.clicked("▶ 지금 실행  (대기 없음)")
    def run_now(self, _):
        if self._proc and self._proc.poll() is None:
            rumps.notification("🎵 수노", "이미 실행 중", "완료 후 다시 시도하세요.")
            return
        config = load_config()
        pm = _get_pm(config)
        pm.scan_input()
        if not pm.get_pending():
            rumps.notification("🎵 수노", "대기 없음",
                               "입력 폴더(📂)에 이미지를 넣어주세요.")
            return
        self._start_next_project(config)

    def _start_next_project(self, config: dict):
        pm = _get_pm(config)
        pending = pm.get_pending()
        if not pending:
            return
        project_id = pending[0]["id"]
        keyword    = pending[0].get("keyword", project_id)

        _append_log(f"프로젝트 시작: {project_id}")
        self.status_item.title = f"⏳ {keyword[:20]}..."

        api_key = config.get("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        env = {**os.environ}
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key

        log_fd = LOG_FILE.open("a", encoding="utf-8")
        self._log_fd = log_fd
        self._proc = subprocess.Popen(
            [sys.executable, str(SCRIPT_DIR / "suno_pipeline.py"),
             "--project-id", project_id],
            stdout=log_fd, stderr=log_fd, env=env,
        )
        self._refresh_menu()

        # 완료 체크 타이머 (10초 간격)
        if hasattr(self, "_done_timer") and self._done_timer:
            self._done_timer.stop()
        self._done_timer = rumps.Timer(self._check_proc_done, 10)
        self._done_timer.start()

    # ------------------------------------------------------------------
    # 메뉴 콜백
    # ------------------------------------------------------------------

    @rumps.clicked("📂 입력 폴더 열기")
    def open_input(self, _):
        config = load_config()
        d = Path(config.get("projects_root", "~/SunoProjects")).expanduser() / "input"
        d.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(d)])

    @rumps.clicked("📁 결과물 폴더 열기")
    def open_output(self, _):
        config = load_config()
        d = Path(config.get("projects_root", "~/SunoProjects")).expanduser() / "projects"
        d.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(d)])

    @rumps.clicked("📋 로그 보기")
    def show_log(self, _):
        tail = _read_log_tail(50)
        # AppleScript 특수문자 이스케이프
        escaped = (tail.replace("\\", "\\\\")
                       .replace('"', '\\"')
                       .replace("\n", "\\n"))
        result = _osascript(
            f'button returned of (display dialog "{escaped}" '
            f'with title "수노 자동화 — 최근 로그" '
            f'buttons {{"로그 파일 열기", "닫기"}} default button "닫기")'
        )
        if result == "로그 파일 열기" and LOG_FILE.exists():
            subprocess.Popen(["open", str(LOG_FILE)])

    @rumps.clicked("❓ 사용 방법")
    def show_help(self, _):
        subprocess.Popen([sys.executable,
                          str(SCRIPT_DIR / "suno_settings.py"), "--help-tab"])

    @rumps.clicked("🔄 UI 재학습")
    def relearn(self, _):
        config = load_config()
        api_key = config.get("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            rumps.notification("⚙️ API 키 없음", "", "설정(⚙️)에서 API 키를 먼저 입력하세요.")
            return
        env = {**os.environ, "ANTHROPIC_API_KEY": api_key}
        log_fd = LOG_FILE.open("a", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(SCRIPT_DIR / "suno_learn.py"), "--force"],
            stdout=log_fd, stderr=log_fd, env=env,
        )
        rumps.notification("🔄 UI 재학습", "시작됨", "📋 로그 보기에서 진행 상황을 확인하세요.")

    @rumps.clicked("⚙️ 설정...")
    def open_settings(self, _):
        subprocess.Popen([sys.executable, str(SCRIPT_DIR / "suno_settings.py")])

    # ------------------------------------------------------------------
    # 첫 실행 체크
    # ------------------------------------------------------------------

    def _check_first_run(self):
        if not (SCRIPT_DIR / "suno_actions.json").exists():
            rumps.notification(
                "🎵 수노 자동화",
                "최초 실행 — UI 학습 필요",
                "메뉴 → 🔄 UI 재학습을 먼저 실행하세요.",
            )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SunoMenuBar().run()
