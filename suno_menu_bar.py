"""
수노 자동화 메뉴바 앱
macOS 상단 메뉴바에 🎵 아이콘으로 상주합니다.

실행: python suno_menu_bar.py
앱 빌드: bash build_app.sh
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import rumps

BASE_DIR = Path(__file__).parent
RAW_DATA_DIR = BASE_DIR / "raw_data"


# ---------------------------------------------------------------------------
# osascript 헬퍼 (네이티브 macOS 다이얼로그)
# ---------------------------------------------------------------------------
def _osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def ask_text(prompt: str, default: str = "") -> str | None:
    """텍스트 입력 다이얼로그. 취소 시 None 반환."""
    # 따옴표 이스케이프
    prompt_escaped = prompt.replace('"', '\\"')
    default_escaped = default.replace('"', '\\"')
    raw = _osascript(
        f'display dialog "{prompt_escaped}" '
        f'default answer "{default_escaped}" '
        f'with title "🎵 수노 자동화" '
        f'buttons {{"취소", "확인"}} default button "확인"'
    )
    if not raw or "button returned:확인" not in raw:
        return None
    match = re.search(r"text returned:(.*)", raw)
    return match.group(1).strip() if match else None


def ask_select() -> str | None:
    """곡 선택 방식 선택 다이얼로그. 취소 시 None 반환."""
    raw = _osascript(
        'choose from list {"직접 선택 (2곡 모두 보존)", "랜덤 1곡", "긴 곡 자동 선택"} '
        'with title "🎵 선택 방식" '
        'with prompt "곡 선택 방식을 고르세요:" '
        'default items {"직접 선택 (2곡 모두 보존)"}'
    )
    if not raw or raw == "false":
        return None
    if "랜덤" in raw:
        return "random"
    if "긴 곡" in raw:
        return "longest"
    return "manual"


def ask_password(prompt: str) -> str | None:
    """비밀번호(숨김) 입력 다이얼로그. 취소 시 None 반환."""
    prompt_escaped = prompt.replace('"', '\\"')
    raw = _osascript(
        f'display dialog "{prompt_escaped}" '
        f'default answer "" '
        f'with hidden answer '
        f'with title "⚙️ API 키 설정" '
        f'buttons {{"취소", "저장"}} default button "저장"'
    )
    if not raw or "button returned:저장" not in raw:
        return None
    match = re.search(r"text returned:(.*)", raw)
    return match.group(1).strip() if match else None


def load_api_key() -> str:
    """환경변수 또는 .env 파일에서 API 키 로드."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    os.environ["ANTHROPIC_API_KEY"] = key
                    break
    return key


# ---------------------------------------------------------------------------
# 메뉴바 앱
# ---------------------------------------------------------------------------
class SunoMenuBar(rumps.App):
    def __init__(self):
        super().__init__("🎵", quit_button=None)
        self._proc = None

        # API 키 초기 로드
        load_api_key()

        self.status_item = rumps.MenuItem("● 준비됨")
        self.status_item.set_callback(None)  # 클릭 불가 상태 표시용

        self.menu = [
            rumps.MenuItem("▶ 곡 만들기...", callback=self.make_song),
            rumps.MenuItem("🔄 UI 재학습", callback=self.relearn),
            rumps.MenuItem("📁 결과물 폴더 열기", callback=self.open_folder),
            None,
            rumps.MenuItem("⚙️ API 키 설정", callback=self.set_api_key),
            None,
            self.status_item,
            None,
            rumps.MenuItem("종료", callback=rumps.quit_application),
        ]

    # ── 곡 만들기 ──────────────────────────────────────────────
    @rumps.clicked("▶ 곡 만들기...")
    def make_song(self, _):
        # 이미 실행 중이면 알림만 표시
        if self._proc and self._proc.poll() is None:
            rumps.notification("🎵 수노", "이미 실행 중", "현재 생성이 끝난 후 다시 시도하세요.")
            return

        # API 키 확인
        api_key = load_api_key()
        if not api_key:
            rumps.notification("⚙️ API 키 없음", "", "메뉴 → API 키 설정에서 먼저 입력하세요.")
            return

        # 입력 다이얼로그
        title = ask_text("곡 제목:", "서울 봄날 감성")
        if title is None:
            return

        prompt = ask_text("가사 / 프롬프트:", "벚꽃 흩날리는 한강변, 설레는 봄날 오후")
        if prompt is None:
            return

        style = ask_text("스타일 (장르·분위기):", "lofi K-pop chill piano acoustic")
        if style is None:
            return

        select = ask_select()
        if select is None:
            return

        # suno_runner.py 서브프로세스 실행
        env = {**os.environ, "ANTHROPIC_API_KEY": api_key}
        self._proc = subprocess.Popen(
            [
                sys.executable,
                str(BASE_DIR / "suno_runner.py"),
                "--title",  title,
                "--prompt", prompt,
                "--style",  style,
                "--select", select,
                "--skip-ui-check",
            ],
            cwd=str(BASE_DIR),
            env=env,
        )

        self.status_item.title = "⏳ 실행 중..."
        rumps.notification("🎵 수노", "시작", f'"{title}" 생성을 시작합니다.\nChrome에서 suno.com/create를 열어두세요.')

        # 10초마다 완료 여부 확인
        self._timer = rumps.Timer(self._check_done, 10)
        self._timer.start()

    def _check_done(self, timer):
        if self._proc and self._proc.poll() is not None:
            code = self._proc.returncode
            self.status_item.title = "● 준비됨"
            if code == 0:
                rumps.notification("🎵 수노", "완료 ✅", "MP3 다운로드가 완료됐습니다.\n결과물 폴더를 확인하세요.")
            else:
                rumps.notification("🎵 수노", "오류 ❌", f"실행 중 오류가 발생했습니다. (코드 {code})")
            timer.stop()

    # ── UI 재학습 ───────────────────────────────────────────────
    @rumps.clicked("🔄 UI 재학습")
    def relearn(self, _):
        api_key = load_api_key()
        env = {**os.environ, "ANTHROPIC_API_KEY": api_key}
        subprocess.Popen(
            [sys.executable, str(BASE_DIR / "suno_learn.py"), "--force"],
            cwd=str(BASE_DIR),
            env=env,
        )
        rumps.notification("🔄 UI 재학습", "시작", "터미널 창에서 진행 상황을 확인하세요.")

    # ── 결과물 폴더 열기 ────────────────────────────────────────
    @rumps.clicked("📁 결과물 폴더 열기")
    def open_folder(self, _):
        RAW_DATA_DIR.mkdir(exist_ok=True)
        subprocess.run(["open", str(RAW_DATA_DIR)])

    # ── API 키 설정 ─────────────────────────────────────────────
    @rumps.clicked("⚙️ API 키 설정")
    def set_api_key(self, _):
        key = ask_password("Anthropic API 키를 입력하세요\n(sk-ant-api03-...)")
        if not key:
            return

        # .env 파일 업데이트
        env_file = BASE_DIR / ".env"
        lines = env_file.read_text().splitlines() if env_file.exists() else []
        lines = [l for l in lines if not l.startswith("ANTHROPIC_API_KEY")]
        lines.append(f"ANTHROPIC_API_KEY={key}")
        env_file.write_text("\n".join(lines) + "\n")

        # 현재 프로세스 환경변수도 업데이트
        os.environ["ANTHROPIC_API_KEY"] = key

        rumps.notification("⚙️ API 키", "저장 완료 ✅", ".env 파일에 저장됐습니다.")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    SunoMenuBar().run()
