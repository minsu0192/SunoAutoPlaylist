"""
수노 자동 실행 스크립트
학습된 좌표(suno_actions.json)를 바탕으로 pyautogui로 자동 조작합니다.

실행 플로우 (9단계):
  1. Advanced 탭 클릭
  2. Lyrics 입력
  3. Styles 입력
  4. 스크롤 다운 (Song Title / Create 버튼 노출)
  5. Song Title 입력
  6. Create 버튼 클릭
  7. 생성 대기 (~100초)
  8. 생성된 2곡 MP3 다운로드 (Claude Haiku로 ⋮ 버튼 위치 탐지)
  9. 다운로드 파일을 raw_data/{날짜}_{제목}/ 폴더로 이동

실행: python3.11 suno_runner.py --title "제목" --prompt "가사" --style "스타일"
      python3.11 suno_runner.py  (대화형 입력)
"""

import argparse
import base64
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pyautogui

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

ACTIONS_FILE = Path(__file__).parent / "suno_actions.json"
RAW_DATA_DIR = Path(__file__).parent / "raw_data"

# pyautogui 안전 설정
pyautogui.PAUSE = 0.5
pyautogui.FAILSAFE = True  # 마우스를 왼쪽 상단 모서리로 이동하면 즉시 중단


# ---------------------------------------------------------------------------
# 기본 헬퍼
# ---------------------------------------------------------------------------
def load_actions() -> dict:
    if not ACTIONS_FILE.exists():
        print("❌ 학습 데이터가 없습니다.")
        print("   먼저 python3.11 suno_learn.py 를 실행해주세요.")
        sys.exit(1)
    return json.loads(ACTIONS_FILE.read_text())


def click(coords: dict, label: str = ""):
    x, y = int(coords["x"]), int(coords["y"])
    print(f"  클릭: {label} ({x}, {y})")
    pyautogui.moveTo(x, y, duration=0.4)
    pyautogui.click()
    time.sleep(0.5)


def type_text(text: str):
    pyautogui.hotkey("command", "a")
    time.sleep(0.1)
    pyautogui.typewrite(text, interval=0.03)


def scroll_panel(ref_coords: dict, amount: int = -5):
    """ref_coords 아래에서 스크롤."""
    x = int(ref_coords["x"])
    y = int(ref_coords["y"]) + 60
    pyautogui.moveTo(x, y, duration=0.3)
    pyautogui.scroll(amount)
    time.sleep(0.8)


# ---------------------------------------------------------------------------
# 생성 대기
# ---------------------------------------------------------------------------
def wait_for_generation(wait_sec: int = 100):
    print(f"\n[7/9] 음악 생성 대기 중 (최대 {wait_sec}초)...")
    print("      (Suno는 1곡당 약 1~2분 소요됩니다)")
    for i in range(wait_sec):
        bar = "█" * (i * 20 // wait_sec) + "░" * (20 - i * 20 // wait_sec)
        print(f"\r  [{bar}] {i+1}/{wait_sec}초", end="", flush=True)
        time.sleep(1)
    print(f"\r  [{'█'*20}] {wait_sec}/{wait_sec}초 완료")
    time.sleep(3)  # 렌더링 여유


# ---------------------------------------------------------------------------
# 다운로드 감지: 스냅샷 방식 (~/Downloads 변경 감시)
# ---------------------------------------------------------------------------

def snapshot_downloads() -> set:
    """현재 ~/Downloads 의 MP3 파일 집합을 반환."""
    d = Path.home() / "Downloads"
    return set(d.glob("*.mp3")) if d.exists() else set()


def wait_for_downloads_complete(before: set, expected: int,
                                timeout: int = 180) -> list[Path]:
    """
    모든 다운로드 클릭 완료 후 호출.
    새 MP3가 expected 개수만큼 안정화(크기 변화 없음)될 때까지 대기.
    """
    d = Path.home() / "Downloads"
    print(f"  ⏳ 다운로드 완료 대기 중... ({expected}개, 최대 {timeout}초)")
    deadline = time.time() + timeout

    while time.time() < deadline:
        new_files = set(d.glob("*.mp3")) - before
        stable = _stable_files(new_files)
        elapsed = int(timeout - (deadline - time.time()))
        print(f"\r  {len(stable)}/{expected}개 완료 ({elapsed}s)...", end="", flush=True)
        if len(stable) >= expected:
            print()
            return stable
        time.sleep(2)

    print()
    # 타임아웃 — 지금까지 안정화된 것이라도 반환
    new_files = set(d.glob("*.mp3")) - before
    stable = _stable_files(new_files)
    if stable:
        print(f"  ⚠️  타임아웃 — {len(stable)}개만 수집됨 (예상 {expected}개)")
    else:
        print("  ❌ 다운로드된 파일을 찾지 못했습니다.")
    return stable


def _stable_files(files: set) -> list[Path]:
    """크기가 안정화된 파일(다운로드 완료)만 반환."""
    stable = []
    for f in files:
        try:
            s1 = f.stat().st_size
            time.sleep(0.5)
            s2 = f.stat().st_size
            if s1 == s2 and s1 > 0:
                stable.append(f)
        except Exception:
            pass
    return stable


def click_download_for_song(actions: dict, song_idx: int, y_offset: int = 0):
    """
    학습된 song_options_btn → download_btn 좌표를 사용해 곡 다운로드.
    song_idx: 0=첫 번째 곡, 1=두 번째 곡 (y 오프셋으로 구분)
    y_offset: 두 번째 곡은 첫 번째 곡 카드 높이만큼 아래
    """
    if "song_options_btn" not in actions or "download_btn" not in actions:
        print(f"  ⚠️  학습된 다운로드 좌표 없음. 설정 → 고급 → 🎬 녹화 학습을 실행하세요.")
        return False

    # ... 버튼 클릭 (두 번째 곡은 y_offset 만큼 아래)
    ox = int(actions["song_options_btn"]["x"])
    oy = int(actions["song_options_btn"]["y"]) + y_offset
    print(f"  ⋮ 버튼 클릭 (곡 {song_idx+1}): ({ox}, {oy})")
    pyautogui.moveTo(ox, oy, duration=0.4)
    pyautogui.click()
    time.sleep(0.8)

    # 다운로드 버튼 클릭
    dx = int(actions["download_btn"]["x"])
    dy = int(actions["download_btn"]["y"])
    print(f"  다운로드 클릭: ({dx}, {dy})")
    pyautogui.moveTo(dx, dy, duration=0.3)
    pyautogui.click()
    time.sleep(1.5)
    return True


# ---------------------------------------------------------------------------
# 곡 선택 (다운로드 후 적용)
# ---------------------------------------------------------------------------
DISCARD_DIR = RAW_DATA_DIR / "_should_delete"


def select_song(moved: list[Path], mode: str) -> list[Path]:
    """
    mode:
      manual  — 2곡 모두 보존, 사용자가 나중에 직접 선택
      random  — 1곡 랜덤 보존, 나머지는 _should_delete/ 로 이동
      longest — 파일 크기가 큰 쪽 보존, 나머지는 _should_delete/ 로 이동
    반환: 최종 보존된 파일 리스트
    """
    if len(moved) <= 1 or mode == "manual":
        return moved

    def move_to_discard(f: Path, reason: str):
        DISCARD_DIR.mkdir(parents=True, exist_ok=True)
        dst = DISCARD_DIR / f.name
        shutil.move(str(f), str(dst))
        print(f"  📂 → _should_delete/ ({reason}): {f.name}")

    if mode == "random":
        import random
        kept = random.choice(moved)
        for f in moved:
            if f != kept:
                move_to_discard(f, "랜덤 미선택")
        print(f"  🎲 랜덤 선택: {kept.name}")
        return [kept]

    if mode == "longest":
        sizes = {f: f.stat().st_size for f in moved}
        kept = max(sizes, key=sizes.get)
        for f in moved:
            if f != kept:
                size_mb = sizes[f] / 1024 / 1024
                move_to_discard(f, f"짧은 곡 {size_mb:.1f}MB")
        size_mb = sizes[kept] / 1024 / 1024
        print(f"  📏 긴 곡 선택 ({size_mb:.1f}MB): {kept.name}")
        return [kept]

    return moved


# ---------------------------------------------------------------------------
# 다운로드 파일 이동
# ---------------------------------------------------------------------------
def move_new_mp3s(new_files: list[Path], title: str,
                  output_dir: Path = None) -> list[Path]:
    """
    감지된 새 MP3 파일들을 목적 폴더로 이동.
    output_dir 지정 시 그 폴더에, 없으면 raw_data/{날짜}_{제목}/ 에 저장.
    """
    if not new_files:
        return []

    if output_dir:
        dest_dir = Path(output_dir)
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:40]
        dest_dir = RAW_DATA_DIR / f"{date_str}_{safe_title}"

    dest_dir.mkdir(parents=True, exist_ok=True)

    moved = []
    for src in new_files:
        dst = dest_dir / src.name
        shutil.move(str(src), str(dst))
        print(f"  📁 이동: {src.name} → {dest_dir.name}/")
        moved.append(dst)

    return moved


# ---------------------------------------------------------------------------
# 메인 실행 플로우
# ---------------------------------------------------------------------------
def run(title: str, prompt: str, style: str, api_key: str = "", select: str = "manual",
        output_dir: Path = None, interactive: bool = True) -> list:
    """
    Suno 자동 조작 후 최종 선택된 MP3 파일 경로 리스트 반환.

    Args:
        output_dir:   지정 시 raw_data/ 대신 해당 폴더에 MP3 저장.
        interactive:  False이면 "준비 완료 Enter" 프롬프트 생략 (pipeline 모드).
    """
    actions = load_actions()

    SELECT_LABELS = {"manual": "수동 선택 (2곡 모두 보존)", "random": "랜덤 1곡", "longest": "긴 곡 자동 선택"}
    print()
    print("=" * 55)
    print("수노 자동 실행 시작")
    print("=" * 55)
    print(f"제목  : {title}")
    print(f"스타일: {style}")
    print(f"가사  : {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
    print(f"선택  : {SELECT_LABELS.get(select, select)}")
    print()
    print("⚠️  마우스를 화면 왼쪽 상단으로 이동하면 즉시 중단됩니다.")
    print()
    # Chrome 자동 실행
    print("  Chrome에서 suno.com/create 여는 중...")
    subprocess.Popen(["open", "-a", "Google Chrome", "https://suno.com/create"])
    time.sleep(4)  # 페이지 로딩 대기

    time.sleep(1)

    # [1/9] Advanced 탭 클릭
    print("\n[1/9] Advanced 탭 클릭...")
    click(actions["advanced_tab"], "Advanced 탭")
    time.sleep(0.8)

    # [2/9] Lyrics 입력
    print("[2/9] 가사(Lyrics) 입력...")
    click(actions["lyrics_textarea"], "Lyrics 입력란")
    type_text(prompt)
    time.sleep(0.5)

    # [3/9] Styles 입력
    print("[3/9] 스타일(Styles) 입력...")
    click(actions["style_input"], "Styles 입력란")
    type_text(style)
    time.sleep(0.5)

    # [4/9] 스크롤 다운 (Song Title, Create 버튼 노출)
    print("[4/9] 스크롤 다운 (Song Title / Create 버튼 노출)...")
    scroll_panel(actions["style_input"], amount=-5)

    # [5/9] Song Title 입력 (선택 사항)
    if title and "title_input" in actions:
        print("[5/9] 제목(Song Title) 입력...")
        click(actions["title_input"], "Song Title 입력란")
        type_text(title)
        time.sleep(0.5)
    else:
        print("[5/9] Song Title 건너뜀 (학습 좌표 없음)")

    # [6/9] Create 버튼 클릭
    print("[6/9] Create 버튼 클릭...")
    click(actions["create_button"], "Create 버튼")

    # [7/9] 생성 대기
    wait_for_generation(wait_sec=100)

    # [8/9] 다운로드 — 학습 좌표 사용 + 스냅샷 방식 감지
    dl_count = 2  # Suno는 항상 2곡 생성 (longest/random이어도 2곡 받아서 선택)
    print(f"\n[8/9] MP3 다운로드 ({dl_count}곡)...")

    has_learned = ("song_options_btn" in actions and "download_btn" in actions)
    all_new_files: list[Path] = []

    before = snapshot_downloads()  # 다운로드 전 스냅샷

    if has_learned:
        # 모든 곡 다운로드 버튼 클릭 (먼저 다 끝냄)
        CARD_HEIGHT = 80  # Suno 곡 카드 높이 추정
        for song_idx in range(dl_count):
            y_off = song_idx * CARD_HEIGHT
            click_download_for_song(actions, song_idx, y_offset=y_off)
            time.sleep(1.0)  # 클릭 간 짧은 대기
        # 모든 클릭 완료 후 → 파일 개수 기반 대기
        all_new_files = wait_for_downloads_complete(before, expected=dl_count)
    else:
        # 학습 좌표 없음 → 수동 안내
        print("  ℹ️  다운로드 좌표 미학습 — 수노 페이지에서 직접 각 곡을 다운로드하세요.")
        print("      각 곡의 ⋮ → Download → MP3 Audio 클릭")
        input("  모두 다운로드 후 Enter ▶ ")
        all_new_files = _stable_files(set(Path.home().glob("Downloads/*.mp3")) - before)

    # [9/9] 파일 이동 + 곡 선택
    print("\n[9/9] 다운로드 파일 이동 및 최종 선택...")
    moved = move_new_mp3s(all_new_files, title, output_dir=output_dir)
    final = select_song(moved, mode=select)

    print()
    print("=" * 55)
    if final:
        print(f"✅ 완료! {len(final)}곡 저장됨:")
        for f in final:
            print(f"   📁 {f}")
        if select == "manual" and len(final) == 2:
            print()
            print("  💡 2곡 중 더 좋은 곡을 직접 들어보고 선택하세요.")
            print("     (발음, 길이, 분위기 등을 기준으로 비교)")
    else:
        print("✅ 생성 요청 완료! (파일 이동은 수동으로 확인하세요)")
        print(f"   저장 위치: {RAW_DATA_DIR}/")
    print()
    print("다음 단계: 선택한 곡으로 YouTube 업로드를 진행하세요")
    print("=" * 55)
    return final


# ---------------------------------------------------------------------------
# 시작 시 UI 변경 감지
# ---------------------------------------------------------------------------
def run_startup_ui_check():
    """시작 시 Suno UI 변경 감지 (ANTHROPIC_API_KEY 있을 때만)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return

    try:
        from suno_ui_checker import SunoUIChecker, print_progress
        print("\n수노의 UI 변경사항을 확인하는 중입니다...")
        checker = SunoUIChecker(api_key=api_key)
        report = checker.run_check(progress_callback=print_progress)
        if report.coords_updated:
            print(f"✅ 좌표 자동 업데이트 완료 ({report.tokens_used} 토큰 사용)")
        elif report.changed:
            print(f"⚠️  UI 변경 감지됨 — {report.message}")
        print()
    except Exception as e:
        print(f"[UI 체크 오류] {e} — 기존 좌표로 계속 진행합니다.\n")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="수노 자동 실행")
    parser.add_argument("--title",         help="곡 제목")
    parser.add_argument("--prompt",        help="가사/프롬프트")
    parser.add_argument("--style",         help="음악 스타일")
    parser.add_argument("--select",        choices=["manual", "random", "longest"],
                        default="manual",
                        help=(
                            "곡 선택 방식: "
                            "manual=2곡 모두 보존 후 직접 선택(기본값), "
                            "random=1곡 랜덤 선택, "
                            "longest=파일 크기가 큰 곡(긴 곡) 자동 선택"
                        ))
    parser.add_argument("--skip-ui-check", action="store_true", help="시작 시 UI 변경 감지 건너뜀")
    args = parser.parse_args()

    if not args.skip_ui_check:
        run_startup_ui_check()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    title  = args.title  or input("곡 제목: ").strip()
    prompt = args.prompt or input("가사/프롬프트: ").strip()
    style  = args.style  or input("스타일 (예: lofi hip hop, chill K-pop): ").strip()

    run(title, prompt, style, api_key=api_key, select=args.select)


if __name__ == "__main__":
    main()
