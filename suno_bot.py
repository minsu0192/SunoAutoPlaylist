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
import pyperclip

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
    """클릭. CG 가능하면 네이티브, 아니면 pyautogui."""
    _check_stop()
    if _USE_CG:
        point = CGPointMake(float(x), float(y))
        CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, kCGMouseButtonLeft))
        time.sleep(0.1)
        CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft))
        time.sleep(0.03)
        CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft))
    else:
        pyautogui.moveTo(x, y, duration=0.1)
        time.sleep(0.05)
        pyautogui.click()
    time.sleep(delay)


def _hover(x: int, y: int, delay: float = 0.4) -> None:
    """호버 (클릭 안 함)."""
    _check_stop()
    if _USE_CG:
        CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(
            None, kCGEventMouseMoved, CGPointMake(float(x), float(y)), kCGMouseButtonLeft))
    else:
        pyautogui.moveTo(x, y, duration=0.1)
    time.sleep(delay)


def _type_text(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.05)
    pyautogui.hotkey("command", "v")
    time.sleep(0.15)


def _clear_and_type(x: int, y: int, text: str) -> None:
    _click(x, y, delay=0.15)
    pyautogui.hotkey("command", "a")
    time.sleep(0.05)
    pyautogui.press("delete")
    time.sleep(0.05)
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
        new = sorted(after - before, key=lambda p: p.stat().st_mtime)
        if len(new) >= expected and not downloading:
            return new
        time.sleep(1)
    return sorted(_snapshot_mp3s(d) - before, key=lambda p: p.stat().st_mtime)


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


def _wait_for_song(timeout: int = 120) -> None:
    """곡 생성 대기. 5초 단위 중단 체크."""
    waited = 0
    while waited < timeout:
        _check_stop()
        time.sleep(5)
        waited += 5


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
    time.sleep(0.3)


def check_accessibility() -> bool:
    """클릭이 동작하는지 테스트."""
    if _USE_CG:
        return True
    try:
        pos = pyautogui.position()
        pyautogui.moveTo(pos[0], pos[1])
        return True
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

    _wait_for_song(timeout=120)

    before = _snapshot_mp3s(dl)
    _download_both(actions)
    new = _wait_for_downloads(dl, before, expected=2, timeout=30)
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

    _click(*_coord(actions, "simple_tab"), delay=0.3)
    _click(*_coord(actions, "instrumental_toggle"), delay=0.3)
    if description and "song_desc_input" in actions:
        _clear_and_type(*_coord(actions, "song_desc_input"), description)
    _click(*_coord(actions, "simple_create_btn"), delay=0.5)

    _wait_for_song(timeout=120)

    before = _snapshot_mp3s(dl)
    _download_both(actions)
    new = _wait_for_downloads(dl, before, expected=2, timeout=30)
    return _pick_mp3s(new[:2], pick)
