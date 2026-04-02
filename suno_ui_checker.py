"""
Suno UI 변경 감지 시스템 — 토큰 최소화 3단계 가드
Stage 1: 전체 화면 MD5 → 동일하면 0 토큰
Stage 2: ROI별 해시 → 변경 영역만 추출
Stage 3: 변경 ROI만 claude-haiku-4-5 배치 1회 (~800 토큰 max)
"""

import hashlib
import json
import base64
import io
import time
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

try:
    import pyautogui
    from PIL import Image
    CAPTURE_AVAILABLE = True
except ImportError:
    CAPTURE_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

STATE_FILE = Path(__file__).parent / "suno_state.json"
ACTIONS_FILE = Path(__file__).parent / "suno_actions.json"

# ROI 정의 (화면 비율 기반 — 해상도 독립)
# 실제 수노 UI: 상단 탭(10s/Simple/Advanced/Sounds) → Lyrics → Styles → 스크롤 → Title → Create
ROI_DEFINITIONS = {
    "advanced_tab":  {"x": 0.10, "y": 0.00, "w": 0.35, "h": 0.08},  # 상단 탭 행
    "lyrics_input":  {"x": 0.0,  "y": 0.08, "w": 0.42, "h": 0.38},  # Lyrics 입력
    "style_title":   {"x": 0.0,  "y": 0.45, "w": 0.42, "h": 0.30},  # Styles + 스크롤 영역
    "submit_button": {"x": 0.0,  "y": 0.80, "w": 0.42, "h": 0.18},  # Create 버튼 (스크롤 후)
}


@dataclass
class UICheckReport:
    changed: bool
    changed_rois: list = field(default_factory=list)
    coords_updated: bool = False
    tokens_used: int = 0
    duration_sec: float = 0.0
    message: str = ""


# ---------------------------------------------------------------------------
# ScreenCapture
# ---------------------------------------------------------------------------
class ScreenCapture:
    def take_full_screenshot(self) -> Optional["Image.Image"]:
        if not CAPTURE_AVAILABLE:
            return None
        return pyautogui.screenshot()

    def compute_md5(self, img: "Image.Image") -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return hashlib.md5(buf.getvalue()).hexdigest()

    def crop_roi(self, img: "Image.Image", roi: dict) -> "Image.Image":
        w, h = img.size
        x1 = int(roi["x"] * w)
        y1 = int(roi["y"] * h)
        x2 = int((roi["x"] + roi["w"]) * w)
        y2 = int((roi["y"] + roi["h"]) * h)
        return img.crop((x1, y1, x2, y2))

    def image_to_b64(self, img: "Image.Image", max_width: int = 800) -> str:
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.standard_b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# SunoStateManager
# ---------------------------------------------------------------------------
class SunoStateManager:
    def load(self) -> dict:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save(self, state: dict):
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_coords(self) -> dict:
        if ACTIONS_FILE.exists():
            try:
                return json.loads(ACTIONS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_coords(self, coords: dict):
        ACTIONS_FILE.write_text(json.dumps(coords, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# ClaudeUIAnalyzer
# ---------------------------------------------------------------------------
class ClaudeUIAnalyzer:
    MODEL = "claude-haiku-4-5"

    def __init__(self, api_key: str):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic 패키지가 필요합니다: pip install anthropic")
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze_changed_rois(
        self,
        full_img: "Image.Image",
        changed_rois: list[str],
        existing_coords: dict,
        capture: ScreenCapture,
    ) -> dict:
        """변경된 ROI들을 배치 1회로 분석해 좌표 반환."""
        screen_w, screen_h = full_img.size

        # 이미지 블록 + 텍스트를 한 번에 전송
        content = []

        for roi_name in changed_rois:
            roi_def = ROI_DEFINITIONS.get(roi_name)
            if not roi_def:
                continue
            roi_img = capture.crop_roi(full_img, roi_def)
            b64 = capture.image_to_b64(roi_img, max_width=800)
            roi_x = int(roi_def["x"] * screen_w)
            roi_y = int(roi_def["y"] * screen_h)
            roi_w = int(roi_def["w"] * screen_w)
            roi_h = int(roi_def["h"] * screen_h)

            content.append({
                "type": "text",
                "text": (
                    f"[{roi_name}] 이 이미지는 화면의 ({roi_x},{roi_y}) ~ "
                    f"({roi_x+roi_w},{roi_y+roi_h}) 영역입니다."
                ),
            })
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            })

        content.append({
            "type": "text",
            "text": (
                "위 이미지들에서 각 UI 요소의 중심 좌표를 찾아 JSON으로 반환하세요.\n"
                "반환 형식 (다른 텍스트 없이 JSON만):\n"
                '{"roi_name": {"x": 절대픽셀X, "y": 절대픽셀Y}, ...}\n'
                "찾을 요소:\n"
                "- advanced_tab: 상단 탭 중 'Advanced' 탭 버튼 (10s/Simple/Advanced/Sounds 중 하나)\n"
                "- lyrics_input: 가사(Lyrics) 입력 textarea\n"
                "- style_title: Styles 입력 필드 또는 Song Title 입력 필드\n"
                "- submit_button: Create(생성) 버튼 — 패널 하단에 위치\n"
                "없는 요소는 제외하고 찾은 것만 반환."
            ),
        })

        resp = self.client.messages.create(
            model=self.MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": content}],
        )
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        raw = resp.content[0].text.strip()

        # JSON 파싱
        coords = {}
        try:
            # 코드블록 제거
            if "```" in raw:
                parts = raw.split("```")
                for part in parts[1::2]:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    try:
                        parsed = json.loads(part)
                        break
                    except json.JSONDecodeError:
                        continue
                else:
                    parsed = json.loads(raw.strip())
            else:
                parsed = json.loads(raw.strip())
            for roi_name, pos in parsed.items():
                if isinstance(pos, dict) and "x" in pos and "y" in pos:
                    coords[roi_name] = {"x": int(pos["x"]), "y": int(pos["y"])}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[UIChecker] JSON 파싱 실패: {e}")

        return coords, tokens


# ---------------------------------------------------------------------------
# SunoUIChecker (오케스트레이터)
# ---------------------------------------------------------------------------
class SunoUIChecker:
    STEP_TOTAL = 5

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.capture = ScreenCapture()
        self.state_mgr = SunoStateManager()

    def run_check(self, progress_callback: Optional[Callable] = None) -> UICheckReport:
        t0 = time.time()
        report = UICheckReport(changed=False)

        def progress(step: int, message: str, eta: float = 0):
            if progress_callback:
                progress_callback(step, self.STEP_TOTAL, message, eta)

        # Step 1: 스크린샷
        progress(1, "스크린샷 촬영 중...", 4.0)
        if not CAPTURE_AVAILABLE:
            report.message = "pyautogui/pillow 미설치 — 체크 건너뜀"
            report.duration_sec = time.time() - t0
            progress(self.STEP_TOTAL, report.message, 0)
            return report

        img = self.capture.take_full_screenshot()
        if img is None:
            report.message = "스크린샷 실패"
            report.duration_sec = time.time() - t0
            progress(self.STEP_TOTAL, report.message, 0)
            return report

        # Step 2: 전체 해시 비교
        progress(2, "UI 변경 여부 확인 중...", 3.0)
        state = self.state_mgr.load()
        full_hash = self.capture.compute_md5(img)

        if state.get("full_screen_hash") == full_hash:
            report.message = "UI 변경 없음 (해시 일치)"
            report.duration_sec = time.time() - t0
            progress(self.STEP_TOTAL, "✅ " + report.message, 0)
            return report

        # Step 3: ROI 해시 비교
        progress(3, "변경 영역 분석 중...", 2.5)
        saved_roi_hashes = state.get("roi_hashes", {})
        changed_rois = []
        new_roi_hashes = {}

        for roi_name, roi_def in ROI_DEFINITIONS.items():
            roi_img = self.capture.crop_roi(img, roi_def)
            h = self.capture.compute_md5(roi_img)
            new_roi_hashes[roi_name] = h
            if saved_roi_hashes.get(roi_name) != h:
                changed_rois.append(roi_name)

        if not changed_rois:
            # 전체 해시는 달라도 ROI 해시 모두 동일 → 무관한 영역 변경
            new_state = {**state, "full_screen_hash": full_hash, "roi_hashes": new_roi_hashes}
            self.state_mgr.save(new_state)
            report.message = "UI 변경 없음 (ROI 해시 일치)"
            report.duration_sec = time.time() - t0
            progress(self.STEP_TOTAL, "✅ " + report.message, 0)
            return report

        report.changed = True
        report.changed_rois = changed_rois

        # Step 4: Claude Haiku 분석
        progress(4, f"좌표 재분석 중 ({', '.join(changed_rois)})...", 5.0)
        if not self.api_key:
            report.message = f"API 키 없음 — {len(changed_rois)}개 ROI 변경 감지됨 (수동 재학습 필요)"
            report.duration_sec = time.time() - t0
            progress(self.STEP_TOTAL, "⚠️ " + report.message, 0)
            return report

        if not ANTHROPIC_AVAILABLE:
            report.message = "anthropic 패키지 미설치 — 수동 재학습 필요"
            report.duration_sec = time.time() - t0
            progress(self.STEP_TOTAL, "⚠️ " + report.message, 0)
            return report

        try:
            analyzer = ClaudeUIAnalyzer(api_key=self.api_key)
            existing_coords = self.state_mgr.load_coords()
            new_coords, tokens = analyzer.analyze_changed_rois(
                img, changed_rois, existing_coords, self.capture
            )
            report.tokens_used = tokens

            # 기존 좌표에 새 좌표 병합
            merged = {**existing_coords, **new_coords}
            self.state_mgr.save_coords(merged)
            report.coords_updated = True
        except Exception as e:
            report.message = f"Haiku 분석 실패: {e}"
            report.duration_sec = time.time() - t0
            progress(self.STEP_TOTAL, "❌ " + report.message, 0)
            return report

        # Step 5: 상태 저장
        progress(5, "상태 저장 중...", 0.2)
        new_state = {
            "full_screen_hash": full_hash,
            "roi_hashes": new_roi_hashes,
            "last_checked": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "check_stats": {
                "changed_rois": changed_rois,
                "tokens_used": report.tokens_used,
            },
        }
        self.state_mgr.save(new_state)

        report.message = (
            f"UI 변경 감지 — {len(changed_rois)}개 ROI 업데이트 "
            f"({report.tokens_used} 토큰 사용)"
        )
        report.duration_sec = time.time() - t0
        progress(self.STEP_TOTAL, "✅ " + report.message, 0)
        return report


# ---------------------------------------------------------------------------
# 터미널 진행 표시 헬퍼
# ---------------------------------------------------------------------------
def print_progress(step: int, total: int, message: str, eta: float):
    pct = int(step / total * 100)
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    eta_str = f" (남은 시간 ~{eta:.0f}초)" if eta > 0 else ""
    print(f"\r[{bar}] {pct:3d}%  {message}{eta_str}", end="", flush=True)
    if step == total:
        print()


# ---------------------------------------------------------------------------
# 직접 실행
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    force = "--force" in sys.argv

    if force and STATE_FILE.exists():
        STATE_FILE.unlink()
        print("[강제 초기화] suno_state.json 삭제됨")

    checker = SunoUIChecker(api_key=api_key)
    report = checker.run_check(progress_callback=print_progress)

    print(f"\n결과: {report.message}")
    print(f"변경: {report.changed} | 좌표 업데이트: {report.coords_updated} | "
          f"토큰: {report.tokens_used} | 소요: {report.duration_sec:.2f}초")
