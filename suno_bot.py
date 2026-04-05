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


def _click(x: int, y: int, delay: float = 0.3) -> None:
    _check_stop()
    pyautogui.moveTo(x, y, duration=0.1)
    time.sleep(0.1)
    pyautogui.click()
    time.sleep(delay)


def _hover(x: int, y: int, delay: float = 0.4) -> None:
    _check_stop()
    pyautogui.moveTo(x, y, duration=0.1)
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
    _click(*_coord(actions, dot_key), delay=0.4)
    _hover(*_coord(actions, dl_key), delay=0.4)
    _click(*_coord(actions, mp3_key), delay=1.5)


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


def _wait_and_download(actions: dict, dl_dir: Path, max_wait: int = 360) -> list[Path]:
    """
    곡 생성 대기 + 다운로드.
    150초 대기 → 곡1 다운 → 곡2 다운 → 실패한 곡만 1회 재시도
    """
    before = _snapshot_mp3s(dl_dir)
    _log("곡 생성 대기 시작 (150초)")

    # 150초 기본 대기
    for _ in range(30):
        _check_stop()
        time.sleep(5)

    def _new_count():
        return len(_snapshot_mp3s(dl_dir) - before)

    def _new_files():
        return sorted(_snapshot_mp3s(dl_dir) - before,
                       key=lambda p: p.stat().st_mtime if p.exists() else 0)

    def _wait_no_crdownload(timeout: int = 30) -> None:
        """진행 중인 다운로드(.crdownload)가 모두 끝날 때까지 대기"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            _check_stop()
            if not list(dl_dir.glob("*.crdownload")):
                return
            time.sleep(1)

    def _try_download(dot_key, dl_key, mp3_key, label) -> bool:
        """다운로드 클릭 전 기존 다운로드 완료 대기 → 클릭 → 파일 증가 확인"""
        _wait_no_crdownload()  # 이전 다운로드 끝날 때까지 대기
        count_snap = _new_count()
        _close_popup(actions)
        time.sleep(0.3)
        _log(f"{label} 다운로드 시도")
        _download_one(actions, dot_key, dl_key, mp3_key)
        # 다운로드 완료 대기 (최대 30초)
        _wait_no_crdownload(timeout=30)
        time.sleep(1)  # 파일 시스템 반영 대기
        return _new_count() > count_snap

    # ── 1차 시도: 곡1 → 곡2 ──
    got_first = _try_download("song_dot_btn", "download_item", "mp3_btn", "곡1")
    if got_first:
        _log("곡1 다운로드 성공")
    got_second = _try_download("song_dot_btn_2", "download_item_2", "mp3_btn_2", "곡2")
    if got_second:
        _log("곡2 다운로드 성공")

    # 둘 다 성공하면 끝
    if got_first and got_second:
        result = _new_files()
        _log(f"다운로드 완료: {len(result)}곡")
        return result

    # ── 실패한 곡만 30초 대기 후 1회 재시도 ──
    failed = []
    if not got_first:
        failed.append(("song_dot_btn", "download_item", "mp3_btn", "곡1"))
    if not got_second:
        failed.append(("song_dot_btn_2", "download_item_2", "mp3_btn_2", "곡2"))

    _log(f"{len(failed)}곡 미완료, 30초 대기 후 재시도...")
    for _ in range(6):
        _check_stop()
        time.sleep(5)

    for dot, dl, mp3, label in failed:
        if _try_download(dot, dl, mp3, f"{label} 재시도"):
            _log(f"{label} 재시도 성공")

    result = _new_files()
    _log(f"최종 다운로드: {len(result)}곡")
    return result


# ── 브라우저 ──

def setup_browser() -> None:
    _log("Chrome 설정 + suno.com 열기")
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
    time.sleep(3)  # 페이지 완전 로딩 대기

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

    new = _wait_and_download(actions, dl)
    result = _pick_mp3s(new[:2], vocal_pick)
    _log(f"세션 완료: {len(result)}곡 (pick={vocal_pick})")
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
    dl.mkdir(parents=True, exist_ok=True)
    focus_chrome()
    time.sleep(3)  # 페이지 완전 로딩 대기

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

    new = _wait_and_download(actions, dl)
    result = _pick_mp3s(new[:2], pick)
    _log(f"Instrumental 완료: {len(result)}곡")
    return result
