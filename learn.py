"""
learn.py — Suno.com UI 좌표 학습

모든 단계를 하나씩 끊어서 학습.
대화창에서 안내 → 마우스 올리고 기록 클릭.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pyautogui

ACTIONS_FILE = Path.home() / ".suno_actions.json"


def _dialog(message: str, buttons: list[str], default: str) -> str:
    btn_str = ", ".join(f'"{b}"' for b in buttons)
    script = (
        f'tell application "System Events"\n  activate\nend tell\n'
        f'display dialog "{message}" '
        f'buttons {{{btn_str}}} default button "{default}" '
        f'with title "수노자동화"'
    )
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
        for line in r.stdout.strip().splitlines():
            if "button returned:" in line:
                return line.split("button returned:")[-1].strip()
    except subprocess.TimeoutExpired:
        pass
    return ""


def _alert(message: str):
    script = (
        f'tell application "System Events"\n  activate\nend tell\n'
        f'display alert "수노자동화" message "{message}"'
    )
    try:
        subprocess.run(["osascript", "-e", script], timeout=30)
    except Exception:
        pass


def _notify(message: str):
    try:
        subprocess.run(["osascript", "-e",
            f'display notification "{message}" with title "수노자동화"'], timeout=5)
    except Exception:
        pass


def _record(name: str) -> list[int] | None:
    """마우스 올리고 기록 클릭."""
    btn = _dialog(
        f"마우스를 [{name}]에 올리고\\n'기록' 누르세요",
        ["취소", "기록"], "기록",
    )
    if btn != "기록":
        return None
    time.sleep(0.3)
    x, y = pyautogui.position()
    _notify(f"✅ {name} ({x}, {y})")
    return [x, y]


def _record_with_prep(name: str, prep: str) -> list[int] | None:
    """
    준비 동작 안내 → 준비 완료 후 → 마우스 올리고 기록.
    메뉴를 먼저 열어야 하는 경우 사용.
    """
    btn = _dialog(
        f"먼저: {prep}\\n\\n"
        f"그 다음 [{name}]에 마우스를 올리고\\n"
        f"'기록' 누르세요",
        ["취소", "기록"], "기록",
    )
    if btn != "기록":
        return None
    time.sleep(0.3)
    x, y = pyautogui.position()
    _notify(f"✅ {name} ({x}, {y})")
    return [x, y]


def save_actions(actions: dict):
    with ACTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(actions, f, ensure_ascii=False, indent=2)


def start_learn():
    actions: dict[str, list[int]] = {}

    # ─── 1단계: Advanced 모드 ──────────────────────────────────
    btn = _dialog(
        "【1단계】 Advanced 모드\\n\\n"
        "Chrome에서 suno.com/create를 여세요.\\n"
        "준비되면 '시작'",
        ["취소", "시작"], "시작",
    )
    if btn != "시작":
        return

    for key, name in [
        ("advanced_tab",  "Advanced 탭"),
        ("lyrics_input",  "가사 입력칸"),
        ("style_input",   "스타일 입력칸"),
        ("title_input",   "제목 입력칸"),
        ("create_btn",    "Create 버튼"),
    ]:
        pos = _record(name)
        if pos is None:
            _alert("취소됨")
            return
        actions[key] = pos

    # ─── 2단계: 다운로드 ──────────────────────────────────────
    btn = _dialog(
        "【2단계】 다운로드 학습\\n\\n"
        "같은 이름의 곡이 2개씩 붙어있죠?\\n"
        "(위=첫째, 아래=둘째)\\n\\n"
        "아무 곡 쌍이나 골라서 학습합니다.\\n"
        "준비되면 '다음'",
        ["취소", "다음"], "다음",
    )
    if btn != "다음":
        save_actions(actions)
        _alert("1단계만 저장됨")
        return

    # ── 첫째 곡 다운로드 학습 ──
    btn = _dialog(
        "【첫째 곡 다운로드 학습】\\n\\n"
        "맨 위 곡(첫째 곡)으로 학습합니다.\\n"
        "준비되면 '다음'",
        ["취소", "다음"], "다음",
    )
    if btn != "다음":
        save_actions(actions)
        return

    pos = _record("첫째 곡의 ... 버튼")
    if pos is None:
        save_actions(actions)
        return
    actions["song_dot_btn"] = pos

    pos = _record_with_prep(
        "Download (첫째 곡)",
        "첫째 곡의 ... 버튼을 클릭해서 메뉴를 여세요",
    )
    if pos is None:
        save_actions(actions)
        return
    actions["download_item"] = pos

    pos = _record_with_prep(
        "MP3 (첫째 곡)",
        "첫째 곡의 ... 클릭 → Download 위에 마우스 올리기",
    )
    if pos is None:
        save_actions(actions)
        return
    actions["mp3_btn"] = pos

    # ── 둘째 곡 다운로드 학습 ──
    btn = _dialog(
        "【둘째 곡 다운로드 학습】\\n\\n"
        "바로 아래 곡(둘째 곡)으로 학습합니다.\\n"
        "준비되면 '다음'",
        ["취소", "다음"], "다음",
    )
    if btn != "다음":
        save_actions(actions)
        return

    pos = _record("둘째 곡의 ... 버튼")
    if pos is None:
        save_actions(actions)
        return
    actions["song_dot_btn_2"] = pos

    pos = _record_with_prep(
        "Download (둘째 곡)",
        "둘째 곡의 ... 버튼을 클릭해서 메뉴를 여세요",
    )
    if pos is None:
        save_actions(actions)
        return
    actions["download_item_2"] = pos

    pos = _record_with_prep(
        "MP3 (둘째 곡)",
        "둘째 곡의 ... 클릭 → Download 위에 마우스 올리기",
    )
    if pos is None:
        save_actions(actions)
        return
    actions["mp3_btn_2"] = pos

    # ─── 3단계: Simple + Instrumental ─────────────────────────
    btn = _dialog(
        "【3단계】 Instrumental 학습\\n\\n"
        "Simple 탭을 클릭해두세요.\\n\\n"
        "준비되면 '시작'\\n"
        "(필요없으면 '건너뛰기')",
        ["취소", "건너뛰기", "시작"], "시작",
    )
    if btn == "취소":
        save_actions(actions)
        _alert("2단계까지 저장됨")
        return

    if btn == "시작":
        for key, name in [
            ("simple_tab",          "Simple 탭"),
            ("song_desc_input",     "Song Description 입력칸"),
            ("instrumental_toggle", "Instrumental 버튼"),
            ("simple_create_btn",   "Create 버튼 (아래쪽)"),
        ]:
            pos = _record(name)
            if pos is None:
                save_actions(actions)
                _alert("도중에 취소됨. 진행분만 저장.")
                return
            actions[key] = pos

    # ─── 저장 ─────────────────────────────────────────────────
    save_actions(actions)

    has_inst = "simple_tab" in actions
    if has_inst:
        _alert("✅ 학습 완료!\\n보컬 + Instrumental 모두 준비됨")
    else:
        _alert("✅ 학습 완료! (보컬만)")


if __name__ == "__main__":
    start_learn()
