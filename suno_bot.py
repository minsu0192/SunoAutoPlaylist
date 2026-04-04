"""
suno_bot.py — CoreGraphics 네이티브 이벤트로 Suno.com 자동 조작

학습 데이터: ~/.suno_actions.json
다운로드 폴더: ~/SunoOutput/downloads/ (Chrome 실행 시 AppleScript로 설정)
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

import pyautogui
import pyperclip
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

pyautogui.FAILSAFE = True  # 마우스를 왼쪽 상단 모서리로 보내면 비상 정지

ACTIONS_FILE = Path.home() / ".suno_actions.json"
SUNO_URL = "https://suno.com/create"
SUNO_DL_DIR = Path.home() / "SunoOutput" / "downloads"

# 중단 플래그 (pipeline에서 설정)
stop_flag: threading.Event | None = None


def _check_stop():
    """중단 플래그 확인. 설정되어 있으면 예외 발생."""
    if stop_flag and stop_flag.is_set():
        raise RuntimeError("사용자에 의해 중단됨")


# ------------------------------------------------------------------ #
# 내부 헬퍼                                                            #
# ------------------------------------------------------------------ #

def load_actions() -> dict:
    if not ACTIONS_FILE.exists():
        raise FileNotFoundError("UI 학습 파일이 없습니다. 'UI 학습'을 먼저 하세요.")
    with ACTIONS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _click(x: int, y: int, delay: float = 0.3) -> None:
    """CoreGraphics 네이티브 클릭."""
    _check_stop()
    point = CGPointMake(float(x), float(y))
    move = CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, move)
    time.sleep(0.15)
    down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, down)
    time.sleep(0.05)
    up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, up)
    time.sleep(delay)


def _hover(x: int, y: int, delay: float = 0.5) -> None:
    """CoreGraphics 네이티브 hover (클릭 안 함)."""
    _check_stop()
    point = CGPointMake(float(x), float(y))
    move = CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, move)
    time.sleep(delay)


def _type_text(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.1)
    pyautogui.hotkey("command", "v")
    time.sleep(0.3)


def _clear_and_type(x: int, y: int, text: str) -> None:
    _click(x, y)
    pyautogui.hotkey("command", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _type_text(text)


def _coord(actions: dict, key: str) -> tuple[int, int]:
    xy = actions[key]
    return int(xy[0]), int(xy[1])


def _snapshot_mp3s(directory: Path) -> set[Path]:
    return set(directory.glob("*.mp3"))


def _wait_for_downloads(directory: Path, before: set[Path], expected: int = 2,
                         timeout: int = 30) -> list[Path]:
    """다운로드 완료를 폴링으로 대기. .crdownload 파일이 사라질 때까지."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        _check_stop()
        # .crdownload 파일이 있으면 아직 다운로드 중
        downloading = list(directory.glob("*.crdownload"))
        after = _snapshot_mp3s(directory)
        new_files = sorted(after - before, key=lambda p: p.stat().st_mtime)
        if len(new_files) >= expected and not downloading:
            return new_files
        time.sleep(2)
    # 타임아웃 — 있는 만큼 반환
    after = _snapshot_mp3s(directory)
    return sorted(after - before, key=lambda p: p.stat().st_mtime)


def _download_one(actions: dict, dot_key: str) -> None:
    _click(*_coord(actions, dot_key), delay=0.5)
    _hover(*_coord(actions, "download_item"), delay=0.5)
    _click(*_coord(actions, "mp3_btn"), delay=2.0)


def _download_both(actions: dict) -> None:
    _download_one(actions, "song_dot_btn")
    _download_one(actions, "song_dot_btn_2")


def _pick_mp3s(files: list[Path], pick: str) -> list[Path]:
    if not files or pick == "both" or len(files) < 2:
        return files
    sorted_by_size = sorted(files, key=lambda p: p.stat().st_size)
    if pick == "shorter":
        kept, rest = sorted_by_size[0], sorted_by_size[1:]
    else:
        kept, rest = sorted_by_size[-1], sorted_by_size[:-1]
    for f in rest:
        try:
            f.unlink()
        except Exception:
            pass
    return [kept]


def _wait_for_song(timeout: int = 180) -> None:
    """곡 생성 대기. 10초 단위로 중단 플래그 체크."""
    waited = 0
    while waited < timeout:
        _check_stop()
        time.sleep(10)
        waited += 10


# ------------------------------------------------------------------ #
# 브라우저 관리                                                         #
# ------------------------------------------------------------------ #

def setup_browser() -> None:
    """파이프라인 시작 전 1회 호출. Chrome 다운로드 경로를 AppleScript로 설정."""
    SUNO_DL_DIR.mkdir(parents=True, exist_ok=True)

    # Chrome Preferences 수정 (Chrome이 닫혀있을 때 반영)
    prefs_file = Path.home() / "Library/Application Support/Google/Chrome/Default/Preferences"
    if prefs_file.exists():
        try:
            prefs = json.loads(prefs_file.read_text(encoding="utf-8"))
            prefs.setdefault("download", {})["default_directory"] = str(SUNO_DL_DIR)
            prefs["download"]["prompt_for_download"] = False
            prefs_file.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # Chrome이 이미 열려있으면 AppleScript로 다운로드 경로 변경
    # chrome://settings 에서 변경하는 대신, 이미 Preferences에 쓴 것을 반영하도록
    # Chrome을 새 탭으로 suno.com 열기
    subprocess.Popen(
        ["open", "-a", "Google Chrome", SUNO_URL],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)


def focus_chrome() -> None:
    subprocess.Popen(
        ["open", "-a", "Google Chrome"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)


def check_accessibility() -> bool:
    try:
        pt = CGPointMake(0.0, 0.0)
        evt = CGEventCreateMouseEvent(None, kCGEventMouseMoved, pt, kCGMouseButtonLeft)
        return evt is not None
    except Exception:
        return False


# ------------------------------------------------------------------ #
# 공개 함수                                                            #
# ------------------------------------------------------------------ #

def run_suno_session(lyrics: str, style: str, title: str, vocal_pick: str = "longer") -> list[Path]:
    """보컬곡 세션: Advanced 모드. 2곡 생성 후 pick 기준으로 선택."""
    actions = load_actions()
    required = ["advanced_tab", "lyrics_input", "style_input",
                "title_input", "create_btn", "song_dot_btn", "song_dot_btn_2",
                "download_item", "mp3_btn"]
    missing = [k for k in required if k not in actions]
    if missing:
        raise RuntimeError(f"UI 학습 항목 누락: {missing}")

    download_dir = SUNO_DL_DIR
    download_dir.mkdir(parents=True, exist_ok=True)

    focus_chrome()

    _click(*_coord(actions, "advanced_tab"), delay=0.5)
    _clear_and_type(*_coord(actions, "lyrics_input"), lyrics)
    _clear_and_type(*_coord(actions, "style_input"), style)
    _clear_and_type(*_coord(actions, "title_input"), title)
    _click(*_coord(actions, "create_btn"), delay=1.0)

    # 곡 생성 대기 (10초 단위로 중단 체크, 최대 180초)
    _wait_for_song(timeout=180)

    # 다운로드 (폴링 방식)
    before = _snapshot_mp3s(download_dir)
    _download_both(actions)
    new_files = _wait_for_downloads(download_dir, before, expected=2, timeout=30)

    return _pick_mp3s(new_files[:2], vocal_pick)


def run_suno_instrumental(description: str = "", pick: str = "both") -> list[Path]:
    """Instrumental 세션: Simple 모드. 2곡 생성."""
    actions = load_actions()
    required = ["simple_tab", "instrumental_toggle", "simple_create_btn",
                "song_dot_btn", "song_dot_btn_2", "download_item", "mp3_btn"]
    missing = [k for k in required if k not in actions]
    if missing:
        raise RuntimeError(f"UI 학습 항목 누락: {missing}")

    download_dir = SUNO_DL_DIR
    download_dir.mkdir(parents=True, exist_ok=True)

    focus_chrome()

    _click(*_coord(actions, "simple_tab"), delay=0.5)
    _click(*_coord(actions, "instrumental_toggle"), delay=0.5)
    if description and "song_desc_input" in actions:
        _clear_and_type(*_coord(actions, "song_desc_input"), description)
    _click(*_coord(actions, "simple_create_btn"), delay=1.0)

    _wait_for_song(timeout=180)

    before = _snapshot_mp3s(download_dir)
    _download_both(actions)
    new_files = _wait_for_downloads(download_dir, before, expected=2, timeout=30)

    return _pick_mp3s(new_files[:2], pick)
