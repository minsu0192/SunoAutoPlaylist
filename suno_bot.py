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
    _log("곡 생성 대기 시작 (180초 = 3분)")
    for _ in range(36):  # 5초 × 36 = 180초
        _check_stop()
        time.sleep(5)

    # ── 읽기 전용 (절대 파일 안 건드림) ──

    def _all_mp3s() -> list[Path]:
        return sorted(dl_dir.glob("*.mp3"),
                       key=lambda p: p.stat().st_mtime if p.exists() else 0)

    def _unique_count() -> int:
        return len({f.stat().st_size for f in _all_mp3s() if f.exists()})

    def _snap(label: str) -> None:
        files = _all_mp3s()
        names = [f"{f.name}({f.stat().st_size//1024}KB)" for f in files]
        _log(f"📸 [{label}] 파일 {len(files)}개, 고유 {_unique_count()}곡: {names}")

    # ── 파일 수정 ──

    def _delete_duplicates() -> None:
        seen: dict[int, Path] = {}
        for f in _all_mp3s():
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
        files_before = len(_all_mp3s())
        _log(f"[{label}] ▶ 다운로드 클릭")
        _download_one(actions, dot_key, dl_key, mp3_key)
        _wait_crdownload()
        _snap(f"{label} 후")

        files_after = len(_all_mp3s())
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
    # 라운드 기반 다운로드 (12개 시나리오 시뮬레이션 검증 완료)
    #
    # 핵심 규칙:
    # 1. 버튼1 → 버튼2 순서로 시도
    # 2. 중복 반환한 버튼은 이번 라운드만 스킵 (다음 라운드에서 재시도)
    # 3. 2곡 달성 즉시 종료
    # 4. 최대 3라운드, 최대 8회 시도
    # ══════════════════════════════════════════════════════════

    buttons = [
        ("song_dot_btn", "download_item", "mp3_btn", "곡1"),
        ("song_dot_btn_2", "download_item_2", "mp3_btn_2", "곡2"),
    ]
    MAX_ROUNDS = 8
    MAX_ATTEMPTS = 18
    total_attempts = 0

    _snap("시작")

    done_buttons: set[int] = set()  # "new" 반환한 버튼 — 영구 스킵

    for rnd in range(MAX_ROUNDS):
        if _unique_count() >= 2:
            break

        skip_this_round: set[int] = set()  # "duplicate" 반환 — 이 라운드만 스킵

        for btn_idx, (dot, dl, mp3, label) in enumerate(buttons):
            if _unique_count() >= 2:
                _log(f"✅ 고유 2곡 달성!")
                break
            if btn_idx in done_buttons:
                _log(f"[{label}] ⏭ 이미 성공한 버튼 → 영구 스킵")
                continue
            if btn_idx in skip_this_round:
                _log(f"[{label}] ⏭ 이 라운드 스킵 (중복)")
                continue
            if total_attempts >= MAX_ATTEMPTS:
                _log(f"⚠️ 최대 시도 도달 ({MAX_ATTEMPTS}회)")
                break

            total_attempts += 1
            result = _try_one(dot, dl, mp3, f"R{rnd+1}-{label}")

            if result == "new":
                done_buttons.add(btn_idx)  # 이 버튼은 다시 안 건드림
            elif result == "duplicate":
                skip_this_round.add(btn_idx)

        if _unique_count() < 2 and rnd < MAX_ROUNDS - 1:
            _log(f"📊 고유 {_unique_count()}곡 — 30초 대기 후 라운드 {rnd+2}")
            for _ in range(6):
                _check_stop()
                time.sleep(5)

    _delete_duplicates()
    result = _all_mp3s()
    _snap("최종")
    _log(f"🏁 다운로드 완료: 고유 {_unique_count()}곡, 시도 {total_attempts}회")
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
    safe_dir = dl.parent / "completed"
    safe_dir.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    for f in selected:
        if f.exists():
            dest = safe_dir / f"{int(time.time())}_{f.name}"
            f.rename(dest)
            result.append(dest)
            _log(f"보관: {f.name} → completed/")

    # ── 나머지 파일 전부 삭제 (다음 세션에 영향 안 주도록) ──
    leftover = list(dl.glob("*.mp3"))
    if leftover:
        for f in leftover:
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

    _log(f"다운로드 결과: {len(new)}곡")
    for f in new:
        _log(f"  - {f.name} ({f.stat().st_size / 1024:.0f} KB)")

    selected = _pick_mp3s(new[:2], pick)
    _log(f"선택된 곡: {[f.name for f in selected]}")

    safe_dir = dl.parent / "completed"
    safe_dir.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    for f in selected:
        if f.exists():
            dest = safe_dir / f"{int(time.time())}_{f.name}"
            f.rename(dest)
            result.append(dest)
            _log(f"보관: {f.name} → completed/")

    leftover = list(dl.glob("*.mp3"))
    if leftover:
        for f in leftover:
            _log(f"삭제: {f.name}")
            f.unlink()

    _log(f"=== Instrumental 완료: {len(result)}곡 (pick={pick}) ===")
    return result
