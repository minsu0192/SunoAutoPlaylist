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


def _find_python() -> str:
    """실행 가능한 Python 인터프리터 경로 반환."""
    # 가상환경 우선
    venv_py = SCRIPT_DIR / ".venv" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py)
    for candidate in ["python3.11", "python3", "python"]:
        r = subprocess.run(["which", candidate], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip()
    return sys.executable


def _open_python_script(script_path: str, extra_args: list = None):
    """tkinter 설정 창처럼 GUI 스크립트를 올바른 Python으로 실행."""
    python = _find_python()
    cmd = [python, script_path] + (extra_args or [])
    subprocess.Popen(cmd, env={**os.environ})


def _open_terminal_command(cmd: str):
    """macOS Terminal을 열고 주어진 명령어를 실행."""
    apple_script = f'''
    tell application "Terminal"
        activate
        do script "{cmd}"
    end tell
    '''
    subprocess.Popen(["osascript", "-e", apple_script])


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
        if LOG_FILE.exists():
            # 로그 파일을 TextEdit/콘솔로 바로 열기
            subprocess.Popen(["open", str(LOG_FILE)])
        else:
            _osascript(
                'display dialog "아직 로그가 없습니다." '
                'with title "수노 자동화 — 로그" '
                'buttons {"닫기"} default button "닫기"'
            )

    @rumps.clicked("❓ 사용 방법")
    def show_help(self, _):
        _open_python_script(str(SCRIPT_DIR / "suno_settings.py"), ["--help-tab"])

    @rumps.clicked("🔄 UI 재학습")
    def relearn(self, _):
        # 터미널을 열어서 사용자가 직접 상호작용할 수 있게 함
        script_path = str(SCRIPT_DIR / "suno_learn.py")
        _open_terminal_command(
            f"cd '{SCRIPT_DIR}' && python3 '{script_path}' --manual"
        )
        rumps.notification(
            "🔄 UI 재학습",
            "터미널이 열립니다",
            "터미널 안내에 따라 각 요소 위로 마우스를 올리고 Enter를 누르세요."
        )

    @rumps.clicked("⚙️ 설정...")
    def open_settings(self, _):
        _open_python_script(str(SCRIPT_DIR / "suno_settings.py"))

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
