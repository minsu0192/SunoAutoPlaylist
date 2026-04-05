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


def _wait_and_download(actions: dict, dl_dir: Path, max_wait: int = 420) -> list[Path]:
    """
    곡 생성 대기 → 다운로드.

    설계 원칙:
    - 다운로드 시도 전에 반드시 UI 상태 초기화 (Escape + 팝업 닫기)
    - 한 곡 시도 → 성공/실패 확인 → UI 정리 → 다음 곡 시도
    - 실패한 곡만 재시도, 성공한 곡은 절대 다시 안 건드림
    - 이미 받은 파일 수를 기준으로 추가 다운로드 필요 여부 판단
    """
    _log("곡 생성 대기 시작 (150초)")
    for _ in range(30):
        _check_stop()
        time.sleep(5)

    def _get_mp3s() -> list[Path]:
        return sorted(dl_dir.glob("*.mp3"),
                       key=lambda p: p.stat().st_mtime if p.exists() else 0)

    def _unique_sizes() -> set[int]:
        """이미 받은 곡들의 파일 크기 set (중복 판별용)"""
        return {f.stat().st_size for f in _get_mp3s() if f.exists()}

    def _unique_mp3s() -> list[Path]:
        """중복 제거된 mp3 (크기가 같으면 같은 곡)"""
        seen: dict[int, Path] = {}
        for f in _get_mp3s():
            size = f.stat().st_size
            if size not in seen:
                seen[size] = f
            else:
                # 중복 즉시 삭제
                _log(f"중복 삭제: {f.name}")
                f.unlink()
        return list(seen.values())

    def _wait_crdownload_done() -> None:
        time.sleep(3)
        while list(dl_dir.glob("*.crdownload")):
            _check_stop()
            _log("다운로드 진행 중...")
            time.sleep(5)
        time.sleep(1)

    def _reset_ui() -> None:
        _escape_key()
        _escape_key()
        _close_popup(actions)
        time.sleep(0.5)

    def _snapshot() -> str:
        """현재 다운로드 상태 요약"""
        unique = _unique_mp3s()
        names = [f.name for f in unique]
        return f"고유 {len(unique)}곡: {names}"

    def _try_one(dot_key, dl_key, mp3_key, label) -> bool:
        """
        곡 1개 다운로드 시도.
        - 시도 전 스냅샷 체크
        - 다운로드
        - 시도 후 스냅샷 체크 + 중복 감지
        Returns: True=새 고유 곡 추가됨 or 이미 2곡, False=실패
        """
        # ── 시도 전 체크 ──
        before = _unique_mp3s()
        _log(f"[{label}] 시도 전 체크 — {_snapshot()}")
        if len(before) >= 2:
            _log(f"[{label}] 이미 2곡 완료 → 스킵")
            return True

        # ── UI 정리 + 다운로드 ──
        _reset_ui()
        sizes_before = _unique_sizes()
        _log(f"[{label}] 다운로드 클릭")
        _download_one(actions, dot_key, dl_key, mp3_key)
        _wait_crdownload_done()

        # ── 시도 후 체크 ──
        after = _unique_mp3s()  # 중복 자동 삭제됨
        _log(f"[{label}] 시도 후 체크 — {_snapshot()}")

        if len(after) > len(before):
            _log(f"[{label}] 새 고유 곡 추가됨!")
            return True

        # 파일은 받아졌는데 중복이라 삭제된 경우
        new_files = [f for f in _get_mp3s() if f.stat().st_size in sizes_before]
        if len(_get_mp3s()) == len(before):
            # 아무것도 안 받아짐
            _log(f"[{label}] 실패 — 다운로드 안 됨")
            _reset_ui()
            return False

        _log(f"[{label}] 중복 곡 감지 → 이 버튼은 이미 받은 곡")
        _reset_ui()
        return True  # 이 버튼으로는 새 곡을 못 받음, 다른 버튼에서 받아야 함

    # ══════════════════════════════════════════════════════════
    # 메인 흐름: 한 곡씩 받고, 매번 체크
    # ══════════════════════════════════════════════════════════

    _log(f"=== 다운로드 시작 — {_snapshot()} ===")

    # 곡1 시도
    ok1 = _try_one("song_dot_btn", "download_item", "mp3_btn", "곡1")
    _log(f"곡1 결과: {'성공' if ok1 else '실패'} — {_snapshot()}")

    # 곡2 시도 (이미 2곡이면 자동 스킵)
    ok2 = _try_one("song_dot_btn_2", "download_item_2", "mp3_btn_2", "곡2")
    _log(f"곡2 결과: {'성공' if ok2 else '실패'} — {_snapshot()}")

    # ── 2곡 다 있으면 끝 ──
    if len(_unique_mp3s()) >= 2:
        result = _unique_mp3s()
        _log(f"다운로드 완료: {len(result)}곡")
        return result

    # ── 부족하면 30초 대기 후 재시도 ──
    _log(f"부족 — {_snapshot()}, 30초 대기 후 재시도")
    for _ in range(6):
        _check_stop()
        time.sleep(5)

    _log(f"재시도 전 체크 — {_snapshot()}")
    if len(_unique_mp3s()) >= 2:
        return _unique_mp3s()

    # 실패한 곡만 재시도
    if not ok1:
        _log("곡1 재시도")
        _try_one("song_dot_btn", "download_item", "mp3_btn", "곡1 재시도")
        _log(f"곡1 재시도 후 — {_snapshot()}")

    if not ok2 and len(_unique_mp3s()) < 2:
        _log("곡2 재시도")
        _try_one("song_dot_btn_2", "download_item_2", "mp3_btn_2", "곡2 재시도")
        _log(f"곡2 재시도 후 — {_snapshot()}")

    result = _unique_mp3s()
    _log(f"최종: {len(result)}곡")
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
    time.sleep(2)

    # Suno 페이지 새로고침 — 이전 세션 곡이 남아있으면 안 됨
    _log("페이지 새로고침 (이전 세션 곡 제거)")
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
    time.sleep(2)

    # Suno 페이지 새로고침
    _log("페이지 새로고침 (이전 세션 곡 제거)")
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
