"""
수노 UI 자동 학습 스크립트
Claude Vision API로 화면을 분석해서 클릭 좌표를 자동 저장합니다.

실행: python3.11 suno_learn.py
"""

import anthropic
import base64
import io
import json
import os
import re
import time
from pathlib import Path

import pyautogui
from PIL import Image

ACTIONS_FILE = Path(__file__).parent / "suno_actions.json"

STEPS = [
    {
        "key": "custom_mode_toggle",
        "instruction": "Custom Mode 또는 Custom 토글 버튼",
        "prompt_for_claude": (
            "이 화면은 Suno 음악 생성 페이지입니다. "
            "'Custom' 또는 'Custom Mode' 토글 버튼의 중심 좌표를 찾아주세요. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "lyrics_textarea",
        "instruction": "가사/프롬프트 입력창 (Lyrics 또는 큰 텍스트 입력란)",
        "prompt_for_claude": (
            "이 화면은 Suno Custom 모드 음악 생성 페이지입니다. "
            "가사(Lyrics) 또는 프롬프트를 입력하는 가장 큰 텍스트 입력란의 중심 좌표를 찾아주세요. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "style_input",
        "instruction": "스타일 입력창 (Style of Music)",
        "prompt_for_claude": (
            "이 화면은 Suno Custom 모드 음악 생성 페이지입니다. "
            "'Style of Music' 또는 'Style' 입력란의 중심 좌표를 찾아주세요. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "title_input",
        "instruction": "제목 입력창 (Title)",
        "prompt_for_claude": (
            "이 화면은 Suno Custom 모드 음악 생성 페이지입니다. "
            "'Title' 입력란의 중심 좌표를 찾아주세요. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "create_button",
        "instruction": "Create / Generate 버튼",
        "prompt_for_claude": (
            "이 화면은 Suno Custom 모드 음악 생성 페이지입니다. "
            "'Create' 또는 'Generate' 버튼의 중심 좌표를 찾아주세요. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
]


def take_screenshot_b64() -> str:
    screenshot = pyautogui.screenshot()
    buf = io.BytesIO()
    screenshot.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def ask_claude(client: anthropic.Anthropic, screenshot_b64: str, question: str) -> dict | None:
    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64,
                            },
                        },
                        {"type": "text", "text": question},
                    ],
                }
            ],
        )
        text = message.content[0].text.strip()
        # JSON 파싱
        match = re.search(r'\{[^}]+\}', text)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"  [Claude 오류] {e}")
    return None


def manual_click(step_name: str) -> dict:
    print(f"  → 자동 감지 실패. 직접 '{step_name}'을 클릭해주세요.")
    print(f"     3초 후 마우스 위치를 기록합니다...")
    time.sleep(3)
    x, y = pyautogui.position()
    print(f"  → 기록됨: ({x}, {y})")
    return {"x": x, "y": y}


def run_startup_ui_check(api_key: str) -> bool:
    """
    시작 시 UI 변경 감지를 실행합니다.
    변경 없으면 True(재학습 불필요), 변경 있으면 False(재학습 필요) 반환.
    """
    try:
        from suno_ui_checker import SunoUIChecker, print_progress
        print("\n수노의 UI 변경사항을 확인하는 중입니다...")
        checker = SunoUIChecker(api_key=api_key)
        report = checker.run_check(progress_callback=print_progress)
        if not report.changed:
            print(f"✅ {report.message} — 재학습 불필요\n")
            return True
        if report.coords_updated:
            print(f"✅ 좌표 자동 업데이트 완료 ({report.tokens_used} 토큰) — 재학습 불필요\n")
            return True
        print(f"⚠️  UI 변경 감지됨 — 재학습이 필요합니다.\n")
        return False
    except Exception as e:
        print(f"[UI 체크 오류] {e} — 재학습을 진행합니다.\n")
        return False


def main(force: bool = False):
    api_key = os.environ.get("ANTHROPIC_API_KEY") or input("Anthropic API 키를 입력하세요: ").strip()

    # UI 변경 감지: 변경 없으면 재학습 건너뜀 (force=True면 항상 재학습)
    if not force and run_startup_ui_check(api_key):
        print("학습 데이터가 최신 상태입니다. 재학습이 필요하면 --force 옵션을 사용하세요.")
        return

    client = anthropic.Anthropic(api_key=api_key)

    print("=" * 55)
    print("수노 UI 자동 학습")
    print("=" * 55)
    print()
    print("1. 크롬에서 https://suno.com/create 를 열어주세요")
    print("2. Custom Mode를 켜서 입력폼이 다 보이게 해주세요")
    print("3. 준비되면 여기서 Enter를 누르세요")
    print()
    input("준비 완료 후 Enter ▶ ")

    actions = {}

    for step in STEPS:
        print(f"\n[{step['key']}] {step['instruction']} 찾는 중...")
        screenshot_b64 = take_screenshot_b64()

        coords = ask_claude(client, screenshot_b64, step["prompt_for_claude"])

        if coords and "x" in coords and "y" in coords:
            print(f"  ✅ 자동 감지: ({coords['x']}, {coords['y']})")
            # 시각적 확인
            pyautogui.moveTo(coords["x"], coords["y"], duration=0.5)
            confirm = input("  올바른 위치인가요? (y/n): ").strip().lower()
            if confirm != "y":
                coords = manual_click(step["instruction"])
        else:
            coords = manual_click(step["instruction"])

        actions[step["key"]] = coords
        time.sleep(0.3)

    ACTIONS_FILE.write_text(json.dumps(actions, indent=2, ensure_ascii=False))
    print()
    print("=" * 55)
    print(f"✅ 학습 완료! 저장: {ACTIONS_FILE}")
    print()
    print("이제 python3.11 suno_runner.py 로 자동 실행하세요.")
    print("=" * 55)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="수노 UI 자동 학습")
    parser.add_argument("--force", action="store_true", help="UI 체크 건너뛰고 강제 재학습")
    args = parser.parse_args()
    main(force=args.force)
