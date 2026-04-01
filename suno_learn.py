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

# 실제 수노 UI 플로우 (스크린샷 기반):
#   Advanced 탭 클릭 → Lyrics 입력 → Styles 입력 → 스크롤 → Song Title 입력 → Create 클릭
STEPS = [
    {
        "key": "advanced_tab",
        "instruction": "상단 탭 중 'Advanced' 탭 버튼 (10s / Simple / Advanced / Sounds)",
        "prompt_for_claude": (
            "이 화면은 Suno 음악 생성 페이지(suno.com/create)입니다. "
            "화면 왼쪽 패널 상단에 '10s', 'Simple', 'Advanced', 'Sounds' 탭이 나열되어 있습니다. "
            "그 중 'Advanced' 탭 버튼의 중심 좌표를 찾아주세요. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "lyrics_textarea",
        "instruction": "Lyrics 입력창 (가사를 입력하는 가장 큰 텍스트 입력란)",
        "prompt_for_claude": (
            "이 화면은 Suno Advanced 모드 음악 생성 페이지입니다. "
            "'Lyrics' 라고 표시된 가사 입력 textarea의 중심 좌표를 찾아주세요. "
            "왼쪽 패널에서 가장 큰 텍스트 입력 영역입니다. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "style_input",
        "instruction": "Styles 입력창 (음악 스타일을 입력하는 필드)",
        "prompt_for_claude": (
            "이 화면은 Suno Advanced 모드 음악 생성 페이지입니다. "
            "'Styles' 또는 'Style of Music' 라고 표시된 스타일 입력 필드의 중심 좌표를 찾아주세요. "
            "Lyrics 입력란 아래에 위치합니다. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "title_input",
        "instruction": "Song Title 입력창 (스크롤 후 보이는 제목 입력 필드)",
        "prompt_for_claude": (
            "이 화면은 Suno Advanced 모드 음악 생성 페이지입니다. "
            "패널을 아래로 스크롤하면 'Song Title (Optional)' 또는 'Title' 입력란이 보입니다. "
            "해당 제목 입력 필드의 중심 좌표를 찾아주세요. "
            "반드시 JSON 형식으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "create_button",
        "instruction": "Create 버튼 (패널 맨 아래, 스크롤 후 보임)",
        "prompt_for_claude": (
            "이 화면은 Suno Advanced 모드 음악 생성 페이지입니다. "
            "패널 하단에 있는 'Create' 버튼의 중심 좌표를 찾아주세요. "
            "음표 아이콘과 함께 'Create'라고 표시된 버튼입니다. "
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
    print("준비 방법:")
    print("1. 크롬에서 https://suno.com/create 를 열어주세요")
    print("2. 상단 탭에서 'Advanced'를 클릭하세요")
    print("   (10s / Simple / Advanced / Sounds 탭 중 'Advanced')")
    print("3. Lyrics, Styles 입력폼이 보이는 상태로 유지하세요")
    print("   (Song Title, Create 버튼은 스크롤하면 나타남 — 그대로 두세요)")
    print("4. 준비되면 여기서 Enter를 누르세요")
    print()
    input("준비 완료 후 Enter ▶ ")

    actions = {}
    # Song Title과 Create 버튼은 패널 하단 — 학습 전 스크롤 필요
    SCROLL_BEFORE = {"title_input", "create_button"}

    for step in STEPS:
        if step["key"] in SCROLL_BEFORE:
            print(f"\n  ↕️  패널을 아래로 스크롤합니다 (Song Title / Create 버튼 노출)...")
            # 왼쪽 패널 중앙 근처에서 스크롤
            if "style_input" in actions:
                sx, sy = int(actions["style_input"]["x"]), int(actions["style_input"]["y"]) + 60
            else:
                sx, sy = 250, 500
            pyautogui.moveTo(sx, sy, duration=0.3)
            pyautogui.scroll(-5)
            time.sleep(1.0)

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
