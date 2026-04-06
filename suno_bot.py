"""
suno_bot.py — Suno.com 자동 조작

마우스: pyautogui
키보드: osascript (key code)
클립보드: osascript (set the clipboard + key code 9)
"""

from __future__ import annotations

import json
import random
import subprocess
import threading
import time
from pathlib import Path

import pyautogui

# CoreGraphics 시도
_USE_CG = False
try:
    from Quartz import (
        CGEventCreateMouseEvent, CGEventPost, CGPointMake,
        kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGEventMouseMoved,
        kCGMouseButtonLeft, kCGHIDEventTap,
    )
    _test = CGEventCreateMouseEvent(None, kCGEventMouseMoved, CGPointMake(0, 0), kCGMouseButtonLeft)
    if _test is not None:
        _USE_CG = True
except Exception:
    pass

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

ACTIONS_FILE = Path.home() / ".suno_actions.json"
SUNO_URL = "https://suno.com/create"
SUNO_DL_DIR = Path.home() / "SunoOutput" / "downloads"

stop_flag: threading.Event | None = None

# ── 로그 ──
_log_lines: list[str] = []


def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    _log_lines.append(f"[{ts}] {msg}")


def get_log() -> str:
    return "\n".join(_log_lines)


def clear_log():
    _log_lines.clear()


def _check_stop():
    if stop_flag and stop_flag.is_set():
        _log("사용자 중단")
        raise RuntimeError("사용자에 의해 중단됨")


# ── 기본 조작 ──

def load_actions() -> dict:
    if not ACTIONS_FILE.exists():
        raise FileNotFoundError("UI 학습 파일이 없습니다.")
    with ACTIONS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _click(x: int, y: int, delay: float = 0.4) -> None:
    _check_stop()
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(0.15)
    pyautogui.click()
    time.sleep(delay)


def _hover(x: int, y: int, delay: float = 0.5) -> None:
    _check_stop()
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(delay)


def _key_code(code: int, using: str = "") -> None:
    if using:
        cmd = f'tell application "System Events" to key code {code} using {using}'
    else:
        cmd = f'tell application "System Events" to key code {code}'
    subprocess.run(["osascript", "-e", cmd], capture_output=True, timeout=5)
    time.sleep(0.15)


def _type_text(text: str) -> None:
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''set the clipboard to "{safe}"
delay 0.3
tell application "System Events"
    key code 9 using command down
end tell'''
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=30)
    time.sleep(0.3)


def _clear_and_type(x: int, y: int, text: str) -> None:
    _click(x, y, delay=0.3)
    _click(x, y, delay=0.2)
    time.sleep(0.1)
    _key_code(0, using="command down")  # Cmd+A
    time.sleep(0.15)
    _key_code(51)  # Delete
    time.sleep(0.15)
    _type_text(text)


def _coord(actions: dict, key: str) -> tuple[int, int]:
    xy = actions[key]
    return int(xy[0]), int(xy[1])


def _snapshot_mp3s(d: Path) -> set[Path]:
    return set(d.glob("*.mp3"))


def _close_popup(actions: dict) -> None:
    """오른쪽 팝업 패널 닫기."""
    if "popup_close_btn" in actions:
        _click(*_coord(actions, "popup_close_btn"), delay=0.3)
        time.sleep(0.3)


def _download_one(actions: dict, dot_key: str, dl_key: str, mp3_key: str) -> None:
    _click(*_coord(actions, dot_key), delay=0.6)
    _hover(*_coord(actions, dl_key), delay=0.6)
    _click(*_coord(actions, mp3_key), delay=2.0)


def _wait_for_new_files(d: Path, before: set[Path], expected: int, timeout: int = 20) -> list[Path]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _check_stop()
        downloading = list(d.glob("*.crdownload"))
        after = _snapshot_mp3s(d)
        new = sorted(after - before, key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if len(new) >= expected and not downloading:
            return new
        time.sleep(1)
    after = _snapshot_mp3s(d)
    return sorted(after - before, key=lambda p: p.stat().st_mtime if p.exists() else 0)


def _pick_mp3s(files: list[Path], pick: str) -> list[Path]:
    if not files or pick == "both" or len(files) < 2:
        return files
    s = sorted(files, key=lambda p: p.stat().st_size)
    if pick == "shorter":
        kept, rest = s[0], s[1:]
    elif pick == "random":
        kept = random.choice(files)
        rest = [f for f in files if f != kept]
    else:
        kept, rest = s[-1], s[:-1]
    for f in rest:
        try:
            f.unlink()
        except Exception:
            pass
    return [kept]


def _escape_key() -> None:
    """Escape 키 — 열린 메뉴/팝업 닫기"""
    _key_code(53)  # Escape
    time.sleep(0.3)



def _wait_and_download(actions: dict, dl_dir: Path, before_snap: set[Path], max_wait: int = 420) -> list[Path]:
    """
    곡 생성 대기 → 다운로드.

    before_snap: 세션 시작 전 dl_dir의 mp3 스냅샷 (이 파일들은 무시)

    설계 원칙:
    - 다운로드 시도 전에 반드시 UI 상태 초기화 (Escape + 팝업 닫기)
    - 한 곡 시도 → 성공/실패 확인 → UI 정리 → 다음 곡 시도
    - 실패한 곡만 재시도, 성공한 곡은 절대 다시 안 건드림
    - 이미 받은 파일 수를 기준으로 추가 다운로드 필요 여부 판단
    """
    initial_wait = min(240, max_wait)
    _log(f"곡 생성 대기 시작 ({initial_wait}초 = {initial_wait // 60}분 {initial_wait % 60}초)")
    for _ in range(initial_wait // 5):
        _check_stop()
        time.sleep(5)

    # ── 이 세션에서 새로 받은 파일만 추적 ──

    def _new_mp3s() -> list[Path]:
        """세션 시작 후 새로 생긴 mp3만 반환."""
        current = set(dl_dir.glob("*.mp3"))
        new = current - before_snap
        return sorted(new, key=lambda p: p.stat().st_mtime if p.exists() else 0)

    def _unique_count() -> int:
        return len({f.stat().st_size for f in _new_mp3s() if f.exists()})

    def _snap(label: str) -> None:
        files = _new_mp3s()
        names = [f"{f.name}({f.stat().st_size//1024}KB)" for f in files]
        _log(f"📸 [{label}] 새 파일 {len(files)}개, 고유 {_unique_count()}곡: {names}")

    # ── 파일 수정 ──

    def _delete_duplicates() -> None:
        seen: dict[int, Path] = {}
        for f in _new_mp3s():
            s = f.stat().st_size
            if s in seen:
                _log(f"🗑 중복 삭제: {f.name} (={seen[s].name})")
                f.unlink()
            else:
                seen[s] = f

    # ── 유틸 ──

    def _wait_crdownload() -> None:
        time.sleep(3)
        while list(dl_dir.glob("*.crdownload")):
            _check_stop()
            _log("⏳ 다운로드 진행 중...")
            time.sleep(5)
        time.sleep(1)

    def _reset_ui() -> None:
        _escape_key()
        _escape_key()
        _close_popup(actions)
        time.sleep(0.5)

    # ── 다운로드 1회 시도 → "new" | "duplicate" | "failed" ──

    def _try_one(dot_key, dl_key, mp3_key, label) -> str:
        _snap(f"{label} 전")
        unique_before = _unique_count()
        if unique_before >= 2:
            _log(f"[{label}] 이미 2곡 → 스킵")
            return "new"

        _reset_ui()
        files_before = len(_new_mp3s())
        _log(f"[{label}] ▶ 다운로드 클릭")
        _download_one(actions, dot_key, dl_key, mp3_key)
        _wait_crdownload()
        _snap(f"{label} 후")

        files_after = len(_new_mp3s())
        unique_after = _unique_count()

        if files_after <= files_before:
            _log(f"[{label}] ✗ 실패 (파일 없음)")
            _reset_ui()
            return "failed"

        if unique_after > unique_before:
            _log(f"[{label}] ✓ 새 고유 곡!")
            return "new"

        _log(f"[{label}] 🔁 중복! → 삭제")
        _delete_duplicates()
        _reset_ui()
        return "duplicate"

    # ══════════════════════════════════════════════════════════
    # 단순 선형 다운로드 — 루프 없음, 최대 4번 클릭
    #
    # 1차: btn1 시도 → btn2 시도
    # 2곡이면 끝. 아니면 60초 대기.
    # 2차: 실패한 버튼만 딱 1번 재시도
    # 끝. 더 이상 시도 안 함.
    #
    # 성공한 버튼: 절대 다시 안 건드림
    # 중복 버튼: 절대 다시 안 건드림 (같은 곡만 나옴)
    # 실패 버튼만 1회 재시도
    # ══════════════════════════════════════════════════════════

    B1 = ("song_dot_btn", "download_item", "mp3_btn")
    B2 = ("song_dot_btn_2", "download_item_2", "mp3_btn_2")

    _snap("시작")

    # ── 1차: btn1 → btn2 ──
    r1 = _try_one(*B1, "1차-곡1")
    _snap("1차-곡1 후")

    if _unique_count() >= 2:
        _delete_duplicates()
        _log(f"🏁 1차에서 2곡 완료")
        return _new_mp3s()

    r2 = _try_one(*B2, "1차-곡2")
    _snap("1차-곡2 후")

    if _unique_count() >= 2:
        _delete_duplicates()
        _log(f"🏁 1차에서 2곡 완료")
        return _new_mp3s()

    # ── 부족 → 60초 대기 ──
    failed = []
    if r1 == "failed":
        failed.append((B1, "곡1"))
    if r2 == "failed":
        failed.append((B2, "곡2"))
    # "new" → 절대 재시도 안 함
    # "duplicate" → 절대 재시도 안 함 (같은 곡만 나옴)
    # "failed"만 재시도

    if not failed:
        _log(f"🏁 재시도 대상 없음 (고유 {_unique_count()}곡)")
        _delete_duplicates()
        return _new_mp3s()

    retry_wait = max(min(120, max_wait - initial_wait), 30)
    _log(f"📊 고유 {_unique_count()}곡, 실패 {len(failed)}개 → {retry_wait}초 대기 후 재시도")
    for _ in range(retry_wait // 5):
        _check_stop()
        time.sleep(5)

    # ── 2차: 실패한 버튼만 딱 1번 ──
    for keys, name in failed:
        if _unique_count() >= 2:
            break
        _try_one(*keys, f"재시도-{name}")
        _snap(f"재시도-{name} 후")

    _delete_duplicates()
    _snap("최종")
    _log(f"🏁 다운로드 완료: 고유 {_unique_count()}곡")
    return _new_mp3s()


# ── 브라우저 ──

def _get_chrome_download_dir() -> Path:
    """Chrome의 실제 다운로드 경로를 읽어온다.
    Local State에서 가장 최근 활성 프로필을 찾고, 그 프로필의 다운로드 경로를 사용한다."""
    chrome_dir = Path.home() / "Library/Application Support/Google/Chrome"

    # Local State에서 가장 최근 활성 프로필 찾기
    active_profile = "Default"
    local_state = chrome_dir / "Local State"
    if local_state.exists():
        try:
            ls = json.loads(local_state.read_text(encoding="utf-8"))
            info_cache = ls.get("profile", {}).get("info_cache", {})
            best_time = 0
            for name, data in info_cache.items():
                t = data.get("active_time", 0)
                if t > best_time:
                    best_time = t
                    active_profile = name
        except Exception:
            pass

    _log(f"Chrome 활성 프로필: {active_profile}")

    # 활성 프로필의 다운로드 경로 읽기
    prefs_file = chrome_dir / active_profile / "Preferences"
    if prefs_file.exists():
        try:
            prefs = json.loads(prefs_file.read_text(encoding="utf-8"))
            dl_dir = prefs.get("download", {}).get("default_directory", "")
            if dl_dir:
                _log(f"Chrome 다운로드 경로: {dl_dir}")
                return Path(dl_dir)
        except Exception:
            pass

    _log("Chrome 다운로드 경로: ~/Downloads (기본값)")
    return Path.home() / "Downloads"


def setup_browser() -> None:
    global SUNO_DL_DIR
    _log("Chrome 설정 + suno.com 열기")

    # Chrome의 실제 다운로드 경로를 감시 대상으로 사용
    SUNO_DL_DIR = _get_chrome_download_dir()
    SUNO_DL_DIR.mkdir(parents=True, exist_ok=True)

    # 다운로드 폴더 확인 로그
    _log(f"감시 폴더: {SUNO_DL_DIR}")
    _log(f"폴더 존재: {SUNO_DL_DIR.exists()}")
    _log(f"현재 mp3 수: {len(list(SUNO_DL_DIR.glob('*.mp3')))}")

    subprocess.Popen(["open", "-a", "Google Chrome", SUNO_URL],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)


def focus_chrome() -> None:
    subprocess.Popen(["open", "-a", "Google Chrome"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def check_accessibility() -> bool:
    try:
        before = pyautogui.position()
        tx, ty = before[0] + 1, before[1] + 1
        pyautogui.moveTo(tx, ty)
        time.sleep(0.15)
        after = pyautogui.position()
        pyautogui.moveTo(before[0], before[1])
        return after != before
    except Exception:
        return False


# ── 공개 함수 ──

def _snapshot_dl_dir(dl_dir: Path) -> set[Path]:
    """다운로드 폴더의 현재 mp3 파일 목록을 스냅샷으로 저장."""
    if dl_dir.exists():
        return set(dl_dir.glob("*.mp3"))
    return set()


def run_suno_session(lyrics: str, style: str, title: str, vocal_pick: str = "longer") -> list[Path]:
    actions = load_actions()
    required = ["advanced_tab", "lyrics_input", "style_input",
                "title_input", "create_btn",
                "song_dot_btn", "download_item", "mp3_btn",
                "song_dot_btn_2", "download_item_2", "mp3_btn_2"]
    missing = [k for k in required if k not in actions]
    if missing:
        raise RuntimeError(f"UI 학습 항목 누락: {missing}")

    dl = SUNO_DL_DIR
    before_snap = _snapshot_dl_dir(dl)  # 기존 파일 스냅샷 (삭제 안 함)
    _log(f"세션 시작 전 기존 mp3: {len(before_snap)}개")
    focus_chrome()
    time.sleep(2)

    # 페이지 새로고침
    _log("페이지 새로고침")
    _key_code(15, using="command down")  # Cmd+R
    time.sleep(7)  # 페이지 로딩 대기

    _log(f"보컬 세션 시작: {title}")
    _click(*_coord(actions, "advanced_tab"), delay=0.5)
    _log("Advanced 탭 클릭")
    time.sleep(0.5)  # 탭 전환 대기
    _clear_and_type(*_coord(actions, "lyrics_input"), lyrics)
    _log("가사 입력 완료")
    _clear_and_type(*_coord(actions, "style_input"), style)
    _log(f"스타일 입력: {style[:50]}")
    _clear_and_type(*_coord(actions, "title_input"), title)
    _log(f"제목 입력: {title}")
    _click(*_coord(actions, "create_btn"), delay=0.5)
    _log("Create 클릭")

    new = _wait_and_download(actions, dl, before_snap)

    # ── 다운로드 결과 확인 ──
    _log(f"다운로드 결과: {len(new)}곡")
    for f in new:
        _log(f"  - {f.name} ({f.stat().st_size / 1024:.0f} KB)")

    # ── 필터 적용 (shorter/longer/both) ──
    if len(new) >= 2 and vocal_pick != "both":
        _log(f"필터 적용: {vocal_pick}")
    selected = _pick_mp3s(new[:2], vocal_pick)
    _log(f"선택된 곡: {[f.name for f in selected]}")

    # ── 선택된 곡을 completed/로 이동 ──
    safe_dir = Path.home() / "SunoOutput" / "completed"
    safe_dir.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    for idx, f in enumerate(selected):
        if f.exists():
            dest = safe_dir / f"{int(time.time())}_{idx}_{f.name}"
            f.rename(dest)
            result.append(dest)
            _log(f"보관: {f.name} → SunoOutput/completed/")

    # ── 이 세션에서 새로 받은 나머지 파일만 삭제 (기존 파일 보호) ──
    current = set(dl.glob("*.mp3"))
    selected_set = {f for f in selected if f.exists()}
    leftover = current - before_snap - selected_set
    for f in leftover:
        if f.exists():
            _log(f"삭제: {f.name}")
            f.unlink()

    _log(f"=== 세션 완료: {len(result)}곡 선택 (pick={vocal_pick}) ===")
    return result


def run_suno_instrumental(description: str = "", pick: str = "both") -> list[Path]:
    actions = load_actions()
    required = ["simple_tab", "instrumental_toggle", "simple_create_btn",
                "song_dot_btn", "download_item", "mp3_btn",
                "song_dot_btn_2", "download_item_2", "mp3_btn_2"]
    missing = [k for k in required if k not in actions]
    if missing:
        raise RuntimeError(f"UI 학습 항목 누락: {missing}")

    dl = SUNO_DL_DIR
    before_snap = _snapshot_dl_dir(dl)  # 기존 파일 스냅샷 (삭제 안 함)
    _log(f"세션 시작 전 기존 mp3: {len(before_snap)}개")
    focus_chrome()
    time.sleep(2)

    # 페이지 새로고침
    _log("페이지 새로고침")
    _key_code(15, using="command down")  # Cmd+R
    time.sleep(7)

    _log(f"Instrumental 세션 시작: {description[:50] if description else '(설명 없음)'}")
    _click(*_coord(actions, "advanced_tab") if "advanced_tab" in actions
           else _coord(actions, "simple_tab"), delay=0.2)
    _click(*_coord(actions, "simple_tab"), delay=0.3)
    _click(*_coord(actions, "instrumental_toggle"), delay=0.3)
    _log("Simple → Instrumental 토글")
    if description and "song_desc_input" in actions:
        _clear_and_type(*_coord(actions, "song_desc_input"), description)
        _log("Song Description 입력")
    _click(*_coord(actions, "simple_create_btn"), delay=0.5)
    _log("Create 클릭")

    new = _wait_and_download(actions, dl, before_snap)

    _log(f"다운로드 결과: {len(new)}곡")
    for f in new:
        _log(f"  - {f.name} ({f.stat().st_size / 1024:.0f} KB)")

    selected = _pick_mp3s(new[:2], pick)
    _log(f"선택된 곡: {[f.name for f in selected]}")

    safe_dir = Path.home() / "SunoOutput" / "completed"
    safe_dir.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    for idx, f in enumerate(selected):
        if f.exists():
            dest = safe_dir / f"{int(time.time())}_{idx}_{f.name}"
            f.rename(dest)
            result.append(dest)
            _log(f"보관: {f.name} → SunoOutput/completed/")

    # ── 이 세션에서 새로 받은 나머지 파일만 삭제 (기존 파일 보호) ──
    current = set(dl.glob("*.mp3"))
    selected_set = {f for f in selected if f.exists()}
    leftover = current - before_snap - selected_set
    for f in leftover:
        if f.exists():
            _log(f"삭제: {f.name}")
            f.unlink()

    _log(f"=== Instrumental 완료: {len(result)}곡 (pick={pick}) ===")
    return result
