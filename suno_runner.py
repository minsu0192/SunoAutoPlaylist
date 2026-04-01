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
# 다운로드: Claude Haiku로 ⋮ 버튼 위치 탐지
# ---------------------------------------------------------------------------
def take_screenshot_b64_resized(max_width: int = 1280) -> tuple[str, int, int]:
    """스크린샷 찍고 base64 반환. (b64, 원본_w, 원본_h)"""
    from PIL import Image
    img = pyautogui.screenshot()
    orig_w, orig_h = img.size
    if orig_w > max_width:
        ratio = max_width / orig_w
        img = img.resize((max_width, int(orig_h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    return b64, orig_w, orig_h


def find_song_menu_buttons(api_key: str) -> list[dict]:
    """
    Claude Haiku로 스크린샷 분석 →
    오른쪽 Workspace 패널에서 최상단 2개 곡의 ⋮ 버튼 좌표 리스트 반환.
    좌표는 원본 해상도 기준.
    """
    if not ANTHROPIC_AVAILABLE:
        return []

    b64, orig_w, orig_h = take_screenshot_b64_resized(max_width=1280)

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        f"이 화면은 Suno 음악 생성 결과 페이지입니다. "
                        f"화면 크기: {orig_w}×{orig_h}픽셀.\n"
                        "오른쪽 Workspace 패널에 방금 생성된 곡 목록이 있습니다. "
                        "각 곡 항목 오른쪽 끝에 '⋮' (세 점) 메뉴 버튼이 있습니다. "
                        "가장 위에 있는 2개 곡의 ⋮ 버튼 좌표를 원본 해상도 기준으로 반환하세요.\n"
                        "반환 형식 (JSON만, 다른 텍스트 없이):\n"
                        '[{"x": 픽셀X, "y": 픽셀Y}, {"x": 픽셀X, "y": 픽셀Y}]\n'
                        "곡이 1개만 보이면 1개만, 없으면 [] 반환."
                    ),
                },
            ],
        }],
    )
    raw = resp.content[0].text.strip()
    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        if isinstance(parsed, list):
            return [{"x": int(p["x"]), "y": int(p["y"])} for p in parsed if "x" in p and "y" in p]
    except Exception:
        pass
    return []


def click_download_mp3(menu_coords: dict, song_idx: int):
    """
    ⋮ 메뉴 클릭 → 'Download' hover → 'MP3 Audio' 클릭.
    수노 드롭다운 메뉴 항목 순서 기반 상대 오프셋 사용.
    """
    mx, my = int(menu_coords["x"]), int(menu_coords["y"])
    print(f"  ⋮ 메뉴 클릭 (곡 {song_idx}): ({mx}, {my})")

    # ⋮ 버튼에 마우스 이동 후 클릭
    pyautogui.moveTo(mx, my, duration=0.4)
    pyautogui.click()
    time.sleep(0.7)

    # 드롭다운이 열리면 'Download' 항목 찾기 (약 12번째 항목, 항목 높이 ~28px)
    # 드롭다운은 ⋮ 버튼 왼쪽에서 열림 → x 오프셋 -120, y는 항목 순서로
    ITEM_H = 28
    DOWNLOAD_OFFSET_Y = 12 * ITEM_H  # 'Download'는 약 12번째 항목
    MENU_X_OFFSET = -130             # 드롭다운 메뉴가 왼쪽으로 열림

    download_x = mx + MENU_X_OFFSET
    download_y = my + DOWNLOAD_OFFSET_Y

    print(f"  'Download' hover: ({download_x}, {download_y})")
    pyautogui.moveTo(download_x, download_y, duration=0.3)
    time.sleep(0.5)  # 서브메뉴 출현 대기

    # 서브메뉴 'MP3 Audio'는 'Download' 오른쪽 또는 아래에 나타남
    mp3_x = download_x - 120  # 서브메뉴가 왼쪽으로
    mp3_y = download_y         # 첫 번째 서브메뉴 항목

    print(f"  'MP3 Audio' 클릭: ({mp3_x}, {mp3_y})")
    pyautogui.moveTo(mp3_x, mp3_y, duration=0.3)
    pyautogui.click()
    time.sleep(2.0)  # 다운로드 시작 대기


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
def move_downloads_to_raw_data(title: str, expected_count: int = 2) -> list[Path]:
    """
    ~/Downloads 에서 가장 최근 MP3 파일을 raw_data/{날짜}_{제목}/ 으로 이동.
    이동된 파일 경로 리스트 반환.
    """
    downloads_dir = Path.home() / "Downloads"
    if not downloads_dir.exists():
        print("  ⚠️  ~/Downloads 폴더를 찾을 수 없습니다.")
        return []

    # 최근 파일 수집 (최대 30초 전 생성된 mp3)
    now = time.time()
    recent_mp3s = sorted(
        [f for f in downloads_dir.glob("*.mp3") if now - f.stat().st_mtime < 120],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )[:expected_count]

    if not recent_mp3s:
        print("  ⚠️  ~/Downloads에서 최근 MP3 파일을 찾지 못했습니다.")
        return []

    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:40]
    dest_dir = RAW_DATA_DIR / f"{date_str}_{safe_title}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    moved = []
    for i, src in enumerate(recent_mp3s, 1):
        dst = dest_dir / src.name
        shutil.move(str(src), str(dst))
        print(f"  📁 이동: {src.name} → raw_data/{dest_dir.name}/")
        moved.append(dst)

    return moved


# ---------------------------------------------------------------------------
# 메인 실행 플로우
# ---------------------------------------------------------------------------
def run(title: str, prompt: str, style: str, api_key: str = "", select: str = "manual"):
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
    print("준비:")
    print("  1. 크롬에서 https://suno.com/create 를 여세요")
    print("  2. 로그인 상태를 확인하세요")
    input("  3. 준비 완료 후 Enter ▶ ")

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

    # [8/9] 다운로드 (select 모드에 따라 1곡 or 2곡)
    dl_count = 1 if select in ("random", "longest") else 2
    print(f"\n[8/9] 생성된 곡 MP3 다운로드 ({dl_count}곡)...")
    if api_key and ANTHROPIC_AVAILABLE:
        print("  Claude Haiku로 다운로드 버튼 위치 탐지 중...")
        song_btns = find_song_menu_buttons(api_key)
        if song_btns:
            # random 모드: 1곡만 다운로드 (랜덤 선택)
            if select == "random":
                import random as _random
                song_btns = [_random.choice(song_btns)]
            # longest 모드: 2곡 모두 다운로드 후 나중에 크기 비교
            for i, btn in enumerate(song_btns, 1):
                print(f"\n  곡 {i}/{len(song_btns)} 다운로드...")
                click_download_mp3(btn, i)
                time.sleep(1.5)
        else:
            print("  ⚠️  ⋮ 버튼을 자동으로 찾지 못했습니다.")
            print("      수노 페이지에서 직접 각 곡의 ⋮ → Download → MP3 Audio를 클릭하세요.")
    else:
        print("  ℹ️  ANTHROPIC_API_KEY 없음 — 수동 다운로드 필요")
        if select == "random":
            print("      수노 페이지에서 곡 1개의 ⋮ → Download → MP3 Audio를 클릭하세요.")
        else:
            print("      수노 페이지에서 각 곡의 ⋮ → Download → MP3 Audio를 클릭하세요.")
        input("  다운로드 완료 후 Enter ▶ ")

    # [9/9] 파일 이동 + 곡 선택
    print("\n[9/9] 다운로드 파일 이동 및 최종 선택...")
    moved = move_downloads_to_raw_data(title, expected_count=dl_count)
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
