"""
수노 UI 학습 스크립트
3가지 모드:
  --record  : 자연스럽게 워크플로를 진행하며 숫자 키로 요소 마킹 (pynput 필요)
  --manual  : 요소별로 마우스를 올리고 Enter → 좌표 기록
  (기본)    : Claude Vision으로 자동 감지 + 확인
"""

import json
import os
import time
from pathlib import Path

import pyautogui

ACTIONS_FILE = Path(__file__).parent / "suno_actions.json"

# 학습이 필요한 UI 요소 목록
STEPS = [
    {
        "key": "advanced_tab",
        "instruction": "상단 탭 중 'Advanced' 탭 버튼",
        "record_key":  "1",
        "prompt": (
            "이 화면은 Suno 음악 생성 페이지(suno.com/create)입니다. "
            "화면 왼쪽 패널 상단에 '10s', 'Simple', 'Advanced', 'Sounds' 탭이 나열되어 있습니다. "
            "'Advanced' 탭 버튼의 중심 좌표를 JSON으로만 응답하세요: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "lyrics_textarea",
        "instruction": "Lyrics 입력창 (가사 텍스트 입력란)",
        "record_key":  "2",
        "prompt": (
            "Suno Advanced 모드 페이지입니다. "
            "'Lyrics' textarea 중심 좌표를 JSON으로만 응답: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "style_input",
        "instruction": "Styles 입력창 (음악 스타일 필드)",
        "record_key":  "3",
        "prompt": (
            "Suno Advanced 모드 페이지입니다. "
            "'Styles' 스타일 입력 필드 중심 좌표를 JSON으로만 응답: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "title_input",
        "instruction": "Song Title 입력창 (스크롤 후 보임)",
        "record_key":  "4",
        "scroll_before": True,
        "prompt": (
            "Suno Advanced 모드 페이지입니다. "
            "'Song Title (Optional)' 입력란 중심 좌표를 JSON으로만 응답: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "create_button",
        "instruction": "Create 버튼 (패널 맨 아래)",
        "record_key":  "5",
        "scroll_before": True,
        "prompt": (
            "Suno Advanced 모드 페이지입니다. "
            "패널 하단 'Create' 버튼 중심 좌표를 JSON으로만 응답: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "song_options_btn",
        "instruction": "생성된 첫 번째 곡 카드의 '...' (더보기) 버튼",
        "record_key":  "6",
        "wait_prompt": "⏳ Create 클릭 후 곡이 생성될 때까지 기다리세요.\n   곡이 나타나면 첫 번째 곡의 '...' 버튼 위로 마우스를 올리고 아래 안내에 따르세요.",
        "prompt": (
            "Suno 페이지에서 곡이 생성됐습니다. "
            "첫 번째 곡 카드의 '...' 또는 더보기 버튼 좌표를 JSON으로만 응답: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
    {
        "key": "download_btn",
        "instruction": "다운로드 메뉴 항목 (... 클릭 후 나오는 Download 버튼)",
        "record_key":  "7",
        "prompt": (
            "'...' 메뉴가 열린 상태입니다. "
            "'Download' 또는 '다운로드' 메뉴 항목 좌표를 JSON으로만 응답: {\"x\": 숫자, \"y\": 숫자}"
        ),
    },
]

KEY_MAP = {s["record_key"]: s["key"] for s in STEPS}
KEY_LABELS = "\n".join(
    f"  [{s['record_key']}] — {s['instruction']}" for s in STEPS
)


# ─────────────────────────────────────────────────────────────────────────────
# 모드 1: 녹화 모드 (pynput — 자연스럽게 진행하며 숫자 키로 마킹)
# ─────────────────────────────────────────────────────────────────────────────

def record_mode():
    try:
        from pynput import keyboard as kb
    except ImportError:
        print("❌ pynput이 없습니다. 먼저: pip install pynput")
        return

    print("=" * 55)
    print("수노 UI 녹화 학습")
    print("=" * 55)
    print()
    print("사용법:")
    print("  ① Chrome에서 suno.com/create → Advanced 탭을 여세요")
    print("  ② 워크플로를 자연스럽게 진행하면서")
    print("     각 요소 위에 마우스가 있을 때 해당 숫자 키를 누르세요:")
    print()
    print(KEY_LABELS)
    print()
    print("  [0] — 녹화 종료 및 저장")
    print()
    input("준비되면 Enter ▶ ")
    print()
    print("녹화 시작! 숫자 키로 요소를 마킹하세요...")
    print()

    actions = {}
    done = [False]

    def on_press(key):
        try:
            k = getattr(key, "char", None)
            if k is None:
                return
            if k == "0":
                done[0] = True
                return False  # stop listener
            if k in KEY_MAP:
                x, y = pyautogui.position()
                elem = KEY_MAP[k]
                actions[elem] = {"x": x, "y": y}
                name = next(s["instruction"] for s in STEPS if s["key"] == elem)
                print(f"  ✅ [{k}] {name}: ({x}, {y})")
        except Exception:
            pass

    listener = kb.Listener(on_press=on_press)
    listener.start()

    print("(0 키를 누르면 종료됩니다)")
    while not done[0] and listener.is_alive():
        time.sleep(0.2)
    listener.stop()

    if not actions:
        print("\n⚠️  마킹된 요소가 없습니다.")
        return

    # 기존 파일과 병합 (이미 저장된 것은 유지)
    existing = {}
    if ACTIONS_FILE.exists():
        try:
            existing = json.loads(ACTIONS_FILE.read_text())
        except Exception:
            pass
    existing.update(actions)

    ACTIONS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print()
    print("=" * 55)
    print(f"✅ 저장 완료: {ACTIONS_FILE}")
    print(f"   기록된 요소: {', '.join(actions.keys())}")
    missing = [s["key"] for s in STEPS if s["key"] not in existing]
    if missing:
        print(f"⚠️  미기록 요소: {', '.join(missing)}")
        print("   다시 --record 또는 --manual 로 나머지를 기록하세요.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────────────────
# 모드 2: 수동 모드 (마우스 올리고 Enter)
# ─────────────────────────────────────────────────────────────────────────────

def manual_mode():
    print("=" * 55)
    print("수노 UI 수동 학습")
    print("=" * 55)
    print()
    print("Chrome에서 https://suno.com/create → Advanced 탭을 열고")
    print("각 요소 위로 마우스를 올린 뒤 Enter를 누르세요.")
    print()
    input("준비 완료 후 Enter ▶ ")

    actions = {}
    for step in STEPS:
        if step.get("scroll_before") and "style_input" in actions:
            print(f"\n  ↕️  패널 스크롤...")
            sx, sy = int(actions["style_input"]["x"]), int(actions["style_input"]["y"]) + 60
            pyautogui.moveTo(sx, sy, duration=0.3)
            pyautogui.scroll(-5)
            time.sleep(1.0)

        if step.get("wait_prompt"):
            print(f"\n{step['wait_prompt']}")

        print(f"\n[{step['key']}] {step['instruction']}")
        print("  → 마우스를 해당 위치로 올리고 Enter를 누르세요.")
        input("     Enter ▶ ")
        x, y = pyautogui.position()
        actions[step["key"]] = {"x": x, "y": y}
        print(f"  ✅ 기록됨: ({x}, {y})")
        time.sleep(0.3)

    ACTIONS_FILE.write_text(json.dumps(actions, indent=2, ensure_ascii=False))
    print()
    print("=" * 55)
    print(f"✅ 학습 완료! 저장: {ACTIONS_FILE}")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────────────────
# 모드 3: 자동 모드 (Claude Vision)
# ─────────────────────────────────────────────────────────────────────────────

def auto_mode(api_key: str, force: bool = False):
    import anthropic
    import base64
    import io
    import re
    from PIL import Image

    def _screenshot_b64():
        shot = pyautogui.screenshot()
        # RGBA → RGB (JPEG 호환)
        if shot.mode == "RGBA":
            shot = shot.convert("RGB")
        buf = io.BytesIO()
        shot.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()

    def _ask_claude(client, b64, question):
        try:
            msg = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": b64}},
                        {"type": "text", "text": question},
                    ],
                }],
            )
            text = msg.content[0].text.strip()
            m = re.search(r'\{[^}]+\}', text)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"  [Claude 오류] {e}")
        return None

    if not force:
        # 기존 파일 체크
        if ACTIONS_FILE.exists():
            print("학습 데이터가 있습니다. 재학습하려면 --force 옵션을 사용하세요.")
            return

    client = anthropic.Anthropic(api_key=api_key)

    print("=" * 55)
    print("수노 UI 자동 학습 (Claude Vision)")
    print("=" * 55)
    print()
    print("Chrome에서 https://suno.com/create → Advanced 탭을 열고")
    print("Lyrics, Styles 입력폼이 보이는 상태로 유지하세요.")
    print()
    input("준비 완료 후 Enter ▶ ")

    actions = {}
    for step in STEPS:
        if step.get("scroll_before") and "style_input" in actions:
            print(f"\n  ↕️  패널 스크롤...")
            sx, sy = int(actions["style_input"]["x"]), int(actions["style_input"]["y"]) + 60
            pyautogui.moveTo(sx, sy, duration=0.3)
            pyautogui.scroll(-5)
            time.sleep(1.0)

        if step.get("wait_prompt"):
            print(f"\n{step['wait_prompt']}")
            input("  준비되면 Enter ▶ ")

        print(f"\n[{step['key']}] {step['instruction']} 찾는 중...")
        b64 = _screenshot_b64()
        coords = _ask_claude(client, b64, step["prompt"])

        if coords and "x" in coords and "y" in coords:
            print(f"  ✅ 자동 감지: ({coords['x']}, {coords['y']})")
            pyautogui.moveTo(coords["x"], coords["y"], duration=0.4)
            ok = input("  올바른 위치인가요? (y/n): ").strip().lower()
            if ok != "y":
                print("  → 해당 위치로 마우스를 올리고 Enter를 누르세요.")
                input("     Enter ▶ ")
                x, y = pyautogui.position()
                coords = {"x": x, "y": y}
                print(f"  → 수동 기록: ({x}, {y})")
        else:
            print("  → 자동 감지 실패. 마우스를 올리고 Enter를 누르세요.")
            input("     Enter ▶ ")
            x, y = pyautogui.position()
            coords = {"x": x, "y": y}
            print(f"  → 기록됨: ({x}, {y})")

        actions[step["key"]] = coords
        time.sleep(0.3)

    ACTIONS_FILE.write_text(json.dumps(actions, indent=2, ensure_ascii=False))
    print()
    print("=" * 55)
    print(f"✅ 학습 완료! 저장: {ACTIONS_FILE}")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="수노 UI 학습")
    parser.add_argument("--record", action="store_true",
                        help="녹화 모드: 자연스럽게 진행하며 숫자 키로 요소 마킹")
    parser.add_argument("--manual", action="store_true",
                        help="수동 모드: 요소별 마우스 올리고 Enter")
    parser.add_argument("--force",  action="store_true",
                        help="자동 모드에서 강제 재학습")
    args = parser.parse_args()

    if args.record:
        record_mode()
        return

    if args.manual:
        manual_mode()
        return

    # 자동 모드 — API 키 필요
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        cfg = Path.home() / ".suno_config.json"
        if cfg.exists():
            try:
                api_key = json.loads(cfg.read_text())["anthropic_api_key"]
            except Exception:
                pass
    if not api_key:
        print("API 키가 없습니다. --manual 또는 --record 모드를 사용하세요.")
        manual_mode()
        return

    auto_mode(api_key, force=args.force)


if __name__ == "__main__":
    main()
