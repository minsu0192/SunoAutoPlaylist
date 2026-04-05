"""
suno_bot.py — Suno.com 자동 조작

클릭: CoreGraphics 네이티브 → 실패 시 pyautogui fallback
"""

from __future__ import annotations

import json
import random
import subprocess
import threading
import time
from pathlib import Path

import pyautogui

# CoreGraphics 시도 — 번들/권한 문제면 pyautogui fallback
_USE_CG = False
try:
    from Quartz import (
        CGEventCreateMouseEvent,
        CGEventPost,
        CGPointMake,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventMouseMoved,
        kCGMouseButtonLeft,
        kCGHIDEventTap,
    )
    # 실제 이벤트 생성 테스트
    _test = CGEventCreateMouseEvent(None, kCGEventMouseMoved, CGPointMake(0, 0), kCGMouseButtonLeft)
    if _test is not None:
        _USE_CG = True
except Exception:
    pass

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05  # pyautogui 기본 딜레이 줄이기

ACTIONS_FILE = Path.home() / ".suno_actions.json"
SUNO_URL = "https://suno.com/create"
SUNO_DL_DIR = Path.home() / "SunoOutput" / "downloads"

stop_flag: threading.Event | None = None


def _check_stop():
    if stop_flag and stop_flag.is_set():
        raise RuntimeError("사용자에 의해 중단됨")


# ------------------------------------------------------------------ #
# 클릭/호버                                                            #
# ------------------------------------------------------------------ #

def load_actions() -> dict:
    if not ACTIONS_FILE.exists():
        raise FileNotFoundError("UI 학습 파일이 없습니다.")
    with ACTIONS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _click(x: int, y: int, delay: float = 0.3) -> None:
    """pyautogui로 이동 + 클릭. 듀얼 모니터/Retina에서 가장 안정적."""
    _check_stop()
    pyautogui.moveTo(x, y, duration=0.1)
    time.sleep(0.1)
    pyautogui.click()
    time.sleep(delay)


def _hover(x: int, y: int, delay: float = 0.4) -> None:
    """호버 (클릭 안 함)."""
    _check_stop()
    pyautogui.moveTo(x, y, duration=0.1)
    time.sleep(delay)


def _key_code(code: int, using: str = "") -> None:
    """osascript로 키코드 입력."""
    if using:
        cmd = f'tell application "System Events" to key code {code} using {using}'
    else:
        cmd = f'tell application "System Events" to key code {code}'
    subprocess.run(["osascript", "-e", cmd], capture_output=True, timeout=5)
    time.sleep(0.15)


def _type_text(text: str) -> None:
    """클립보드 + key code 9 (Cmd+V)로 붙여넣기. 한국어 OK."""
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''set the clipboard to "{safe}"
delay 0.3
tell application "System Events"
    key code 9 using command down
end tell'''
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=30)
    time.sleep(0.3)


def _clear_and_type(x: int, y: int, text: str) -> None:
    """입력칸 클릭 → 전체선택 → 삭제 → 붙여넣기."""
    _click(x, y, delay=0.3)
    _click(x, y, delay=0.2)
    time.sleep(0.1)
    _key_code(0, using="command down")   # Cmd+A (key code 0 = A)
    time.sleep(0.15)
    _key_code(51)                         # Delete
    time.sleep(0.15)
    _type_text(text)


def _coord(actions: dict, key: str) -> tuple[int, int]:
    xy = actions[key]
    return int(xy[0]), int(xy[1])


def _snapshot_mp3s(d: Path) -> set[Path]:
    return set(d.glob("*.mp3"))


def _wait_for_downloads(d: Path, before: set[Path], expected: int = 2, timeout: int = 30) -> list[Path]:
    """다운로드 완료 폴링."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        _check_stop()
        downloading = list(d.glob("*.crdownload"))
        after = _snapshot_mp3s(d)
        new = sorted(after - before, key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if len(new) >= expected and not downloading:
            return new
        time.sleep(1)
    return sorted(_snapshot_mp3s(d) - before, key=lambda p: p.stat().st_mtime if p.exists() else 0)


def _download_one(actions: dict, dot_key: str, dl_key: str, mp3_key: str) -> None:
    _click(*_coord(actions, dot_key), delay=0.4)
    _hover(*_coord(actions, dl_key), delay=0.4)
    _click(*_coord(actions, mp3_key), delay=1.5)


def _download_both(actions: dict) -> None:
    _download_one(actions, "song_dot_btn", "download_item", "mp3_btn")
    _download_one(actions, "song_dot_btn_2", "download_item_2", "mp3_btn_2")


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


def _wait_and_download(actions: dict, dl_dir: Path, max_wait: int = 300) -> list[Path]:
    """
    곡 생성 대기 + 다운로드를 합쳐서 처리.
    60초 기본 대기 후, 다운로드 시도 → 실패하면 30초 더 기다리고 재시도.
    최대 max_wait초까지 반복.
    """
    before = _snapshot_mp3s(dl_dir)

    # 최소 120초 대기 (Suno 생성 시간)
    for _ in range(24):  # 120초 = 5초 × 24
        _check_stop()
        time.sleep(5)

    # 이후 30초 간격으로 다운로드 시도 (최대 4번 = 추가 120초)
    total_waited = 120
    for attempt in range(4):
        _check_stop()

        # 혹시 팝업이 열려있으면 닫기
        if "popup_close_btn" in actions:
            _click(*_coord(actions, "popup_close_btn"), delay=0.3)
            time.sleep(0.5)

        # 다운로드 시도
        _download_both(actions)
        new = _wait_for_downloads(dl_dir, before, expected=2, timeout=20)

        if new:
            return new

        # 못 받았으면 더 기다리기
        total_waited += 30
        if total_waited >= max_wait:
            break
        for _ in range(6):  # 30초 = 5초 × 6
            _check_stop()
            time.sleep(5)

    # 마지막으로 한번 더 확인
    return sorted(_snapshot_mp3s(dl_dir) - before, key=lambda p: p.stat().st_mtime if p.exists() else 0)


# ------------------------------------------------------------------ #
# 브라우저                                                              #
# ------------------------------------------------------------------ #

def setup_browser() -> None:
    SUNO_DL_DIR.mkdir(parents=True, exist_ok=True)
    prefs_file = Path.home() / "Library/Application Support/Google/Chrome/Default/Preferences"
    if prefs_file.exists():
        try:
            prefs = json.loads(prefs_file.read_text(encoding="utf-8"))
            prefs.setdefault("download", {})["default_directory"] = str(SUNO_DL_DIR)
            prefs["download"]["prompt_for_download"] = False
            prefs_file.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    subprocess.Popen(["open", "-a", "Google Chrome", SUNO_URL],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)


def focus_chrome() -> None:
    subprocess.Popen(["open", "-a", "Google Chrome"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def check_accessibility() -> bool:
    """실제로 마우스를 1px 움직여서 접근성 권한이 있는지 확인."""
    try:
        before = pyautogui.position()
        tx, ty = before[0] + 1, before[1] + 1
        if _USE_CG:
            CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(
                None, kCGEventMouseMoved, CGPointMake(float(tx), float(ty)), kCGMouseButtonLeft))
        else:
            pyautogui.moveTo(tx, ty)
        time.sleep(0.15)
        after = pyautogui.position()
        # 원래 위치로 복귀
        if _USE_CG:
            CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(
                None, kCGEventMouseMoved, CGPointMake(float(before[0]), float(before[1])), kCGMouseButtonLeft))
        else:
            pyautogui.moveTo(before[0], before[1])
        return after != before
    except Exception:
        return False


# ------------------------------------------------------------------ #
# 공개 함수                                                            #
# ------------------------------------------------------------------ #

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
    dl.mkdir(parents=True, exist_ok=True)
    focus_chrome()

    _click(*_coord(actions, "advanced_tab"), delay=0.3)
    _clear_and_type(*_coord(actions, "lyrics_input"), lyrics)
    _clear_and_type(*_coord(actions, "style_input"), style)
    _clear_and_type(*_coord(actions, "title_input"), title)
    _click(*_coord(actions, "create_btn"), delay=0.5)

    # 곡 생성 대기 + 다운로드 (재시도 포함)
    new = _wait_and_download(actions, dl)
    return _pick_mp3s(new[:2], vocal_pick)


def run_suno_instrumental(description: str = "", pick: str = "both") -> list[Path]:
    actions = load_actions()
    required = ["simple_tab", "instrumental_toggle", "simple_create_btn",
                "song_dot_btn", "download_item", "mp3_btn",
                "song_dot_btn_2", "download_item_2", "mp3_btn_2"]
    missing = [k for k in required if k not in actions]
    if missing:
        raise RuntimeError(f"UI 학습 항목 누락: {missing}")

    dl = SUNO_DL_DIR
    dl.mkdir(parents=True, exist_ok=True)
    focus_chrome()

    # Advanced → Simple 전환 (토글 상태 초기화 보장)
    _click(*_coord(actions, "advanced_tab") if "advanced_tab" in actions
           else _coord(actions, "simple_tab"), delay=0.2)
    _click(*_coord(actions, "simple_tab"), delay=0.3)
    # 이제 Instrumental 토글은 항상 OFF 상태 → ON으로 전환
    _click(*_coord(actions, "instrumental_toggle"), delay=0.3)
    if description and "song_desc_input" in actions:
        _clear_and_type(*_coord(actions, "song_desc_input"), description)
    _click(*_coord(actions, "simple_create_btn"), delay=0.5)

    # 곡 생성 대기 + 다운로드 (재시도 포함)
    new = _wait_and_download(actions, dl)
    return _pick_mp3s(new[:2], pick)
