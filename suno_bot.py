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


def _wait_and_download(actions: dict, dl_dir: Path, max_wait: int = 360) -> list[Path]:
    """
    곡 생성 대기 → 곡1 다운 → 곡2 다운 (각각 개별 추적, 중복 다운로드 불가)
    """
    _log("곡 생성 대기 시작 (150초)")
    for _ in range(30):
        _check_stop()
        time.sleep(5)

    # 각 곡의 파일을 개별 추적 (None = 아직 안 받음, Path = 받은 파일)
    song1_file: Path | None = None
    song2_file: Path | None = None

    def _has_crdownload() -> bool:
        return bool(list(dl_dir.glob("*.crdownload")))

    def _wait_download_finish() -> None:
        """.crdownload가 있는 동안 무한 대기 — 다운로드 진행 중"""
        time.sleep(3)  # 다운로드 시작 대기
        while _has_crdownload():
            _check_stop()
            _log("다운로드 진행 중...")
            time.sleep(5)
        time.sleep(1)

    def _try_one_download(dot_key, dl_key, mp3_key, label) -> Path | None:
        """
        곡 1개 다운로드 시도.
        클릭 직전 스냅샷 → 클릭 → 완료 대기 → 직후 스냅샷 비교
        → 새로 생긴 파일 1개를 리턴 (없으면 None)
        """
        # 이전 다운로드 완료 대기
        _wait_download_finish()

        snap_before = _snapshot_mp3s(dl_dir)
        _close_popup(actions)
        time.sleep(0.5)
        _log(f"{label} 다운로드 클릭")
        _download_one(actions, dot_key, dl_key, mp3_key)

        # 다운로드 완료까지 무한 대기
        _wait_download_finish()

        snap_after = _snapshot_mp3s(dl_dir)
        new = snap_after - snap_before
        if new:
            f = sorted(new, key=lambda p: p.stat().st_mtime if p.exists() else 0)[0]
            _log(f"{label} 다운로드 성공: {f.name}")
            return f
        _log(f"{label} 다운로드 실패 (새 파일 없음)")
        return None

    # ── 1차 시도 ──
    song1_file = _try_one_download("song_dot_btn", "download_item", "mp3_btn", "곡1")
    song2_file = _try_one_download("song_dot_btn_2", "download_item_2", "mp3_btn_2", "곡2")

    if song1_file and song2_file:
        _log(f"다운로드 완료: 2곡")
        return [song1_file, song2_file]

    # ── 실패한 곡만 30초 대기 후 1회 재시도 ──
    need_retry = []
    if not song1_file:
        need_retry.append(("song_dot_btn", "download_item", "mp3_btn", "곡1", 1))
    if not song2_file:
        need_retry.append(("song_dot_btn_2", "download_item_2", "mp3_btn_2", "곡2", 2))

    _log(f"{len(need_retry)}곡 미완료, 30초 대기 후 재시도...")
    for _ in range(6):
        _check_stop()
        time.sleep(5)

    for dot, dl, mp3, label, num in need_retry:
        result = _try_one_download(dot, dl, mp3, f"{label} 재시도")
        if result:
            if num == 1:
                song1_file = result
            else:
                song2_file = result

    # 최종 결과 (None 제거)
    final = [f for f in (song1_file, song2_file) if f is not None]
    _log(f"최종 다운로드: {len(final)}곡")
    return final


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

def _clean_dl_dir(dl_dir: Path) -> None:
    """다운로드 폴더를 비워서 이전 세션 파일이 간섭하지 않도록 한다."""
    if dl_dir.exists():
        for f in dl_dir.iterdir():
            try:
                f.unlink()
            except Exception:
                pass
    dl_dir.mkdir(parents=True, exist_ok=True)


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
    _clean_dl_dir(dl)  # 이전 세션 파일 정리
    focus_chrome()
    time.sleep(5)  # 페이지 완전 로딩 대기

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
    # 다운로드된 파일을 안전한 위치로 이동 (다음 세션과 섞이지 않도록)
    saved: list[Path] = []
    safe_dir = dl.parent / "completed"
    safe_dir.mkdir(parents=True, exist_ok=True)
    for f in new:
        if f.exists():
            dest = safe_dir / f"{int(time.time())}_{f.name}"
            f.rename(dest)
            saved.append(dest)
            _log(f"파일 이동: {f.name} → completed/")
    result = _pick_mp3s(saved[:2], vocal_pick)
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
    _clean_dl_dir(dl)  # 이전 세션 파일 정리
    focus_chrome()
    time.sleep(5)  # 페이지 완전 로딩 대기

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
    saved: list[Path] = []
    safe_dir = dl.parent / "completed"
    safe_dir.mkdir(parents=True, exist_ok=True)
    for f in new:
        if f.exists():
            dest = safe_dir / f"{int(time.time())}_{f.name}"
            f.rename(dest)
            saved.append(dest)
            _log(f"파일 이동: {f.name} → completed/")
    result = _pick_mp3s(saved[:2], pick)
    _log(f"Instrumental 완료: {len(result)}곡")
    return result
