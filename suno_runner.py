"""
수노 자동 실행 스크립트
학습된 좌표(suno_actions.json)를 바탕으로 pyautogui로 자동 조작합니다.

실행: python3.11 suno_runner.py --title "제목" --prompt "프롬프트" --style "스타일"
또는: python3.11 suno_runner.py  (대화형 입력)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pyautogui

ACTIONS_FILE = Path(__file__).parent / "suno_actions.json"

# pyautogui 안전 설정
pyautogui.PAUSE = 0.5
pyautogui.FAILSAFE = True  # 마우스를 왼쪽 상단 모서리로 이동하면 중단


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
    pyautogui.typewrite(text, interval=0.03)


def run(title: str, prompt: str, style: str):
    actions = load_actions()

    print()
    print("=" * 50)
    print("수노 자동 실행 시작")
    print("=" * 50)
    print(f"제목  : {title}")
    print(f"프롬프트: {prompt[:50]}...")
    print(f"스타일: {style}")
    print()
    print("⚠️  마우스를 화면 왼쪽 상단으로 이동하면 즉시 중단됩니다.")
    print()
    print("1. 크롬에서 https://suno.com/create 를 열어주세요")
    input("2. 준비 완료 후 Enter ▶ ")

    time.sleep(1)

    # Custom Mode 토글
    print("\n[1/5] Custom Mode 활성화...")
    click(actions["custom_mode_toggle"], "Custom Mode")
    time.sleep(1)

    # 가사/프롬프트 입력
    print("[2/5] 프롬프트 입력...")
    click(actions["lyrics_textarea"], "가사 입력란")
    type_text(prompt)
    time.sleep(0.5)

    # 스타일 입력
    print("[3/5] 스타일 입력...")
    click(actions["style_input"], "스타일 입력란")
    type_text(style)
    time.sleep(0.5)

    # 제목 입력
    print("[4/5] 제목 입력...")
    click(actions["title_input"], "제목 입력란")
    type_text(title)
    time.sleep(0.5)

    # Create 버튼 클릭
    print("[5/5] 생성 버튼 클릭...")
    click(actions["create_button"], "Create 버튼")

    print()
    print("✅ 생성 요청 완료! 수노에서 음악이 생성되고 있습니다.")
    print("   2~3분 후 수노 페이지에서 결과를 확인하세요.")
    print()
    print("⚠️  오류가 발생했거나 UI가 바뀐 경우:")
    print("   python3.11 suno_learn.py 로 재학습 후 다시 시도하세요.")


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


def main():
    parser = argparse.ArgumentParser(description="수노 자동 실행")
    parser.add_argument("--title", help="곡 제목")
    parser.add_argument("--prompt", help="가사/프롬프트")
    parser.add_argument("--style", help="음악 스타일")
    parser.add_argument("--skip-ui-check", action="store_true", help="시작 시 UI 변경 감지 건너뜀")
    args = parser.parse_args()

    if not args.skip_ui_check:
        run_startup_ui_check()

    title = args.title or input("곡 제목: ").strip()
    prompt = args.prompt or input("프롬프트 (가사/분위기): ").strip()
    style = args.style or input("스타일 (예: lofi hip hop, chill): ").strip()

    run(title, prompt, style)


if __name__ == "__main__":
    main()
