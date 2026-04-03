"""
수노 자동화 파이프라인 오케스트레이터
단일 프로젝트를 처음부터 끝까지 처리:
  1. Claude Haiku: 키워드+이미지 → 가사/스타일/설명 생성 (성과 피드백 반영)
  2. Playwright (기본) / pyautogui (fallback): Suno 자동 조작 → MP3 다운로드
  3. FFmpeg:       MP3 + 커버이미지 → MP4
  4. YouTube API:  MP4 업로드 + 플레이리스트 추가

실행: python suno_pipeline.py --project-id 2026-04-01_sunset_calm
      python suno_pipeline.py --next   (큐에서 다음 대기 항목 처리)
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from suno_lyrics_gen import generate_content_safe
from suno_project_manager import ProjectManager


CONFIG_FILE = Path.home() / ".suno_config.json"
UPLOAD_HISTORY_FILE = "upload_history.json"
PERFORMANCE_FILE = "performance_data.json"


def _save_upload_record(projects_root: Path, project_id: str, record: dict):
    """업로드 기록을 히스토리 파일에 추가 (피드백 루프용)."""
    history_path = projects_root / UPLOAD_HISTORY_FILE
    history = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    record["project_id"] = project_id
    history.append(record)
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_performance_hint(projects_root: Path) -> str:
    """성과 데이터에서 상위/하위 패턴을 요약해 프롬프트 힌트로 반환."""
    perf_path = projects_root / PERFORMANCE_FILE
    if not perf_path.exists():
        return ""
    try:
        data = json.loads(perf_path.read_text(encoding="utf-8"))
        top = data.get("top_performers", [])
        low = data.get("low_performers", [])
        if not top and not low:
            return ""

        lines = ["과거 YouTube 성과 데이터 (참고용):"]
        if top:
            lines.append("잘 된 곡:")
            for t in top[:3]:
                lines.append(f"  - {t['keyword']} ({t['style']}) → 조회수 {t['views']}, 좋아요 {t['likes']}")
        if low:
            lines.append("부진한 곡:")
            for l in low[:2]:
                lines.append(f"  - {l['keyword']} ({l['style']}) → 조회수 {l['views']}")
        lines.append("위 데이터를 참고해서 더 나은 가사/스타일을 생성하세요.")
        return "\n".join(lines)
    except Exception:
        return ""


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _osascript_dialog(message: str, title: str = "수노 자동화") -> bool:
    """macOS 확인 다이얼로그. OK=True, 취소=False."""
    script = (
        f'display dialog "{message}" '
        f'with title "{title}" '
        f'buttons {{"취소", "확인"}} '
        f'default button "확인" '
        f'with icon caution'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def _notify(title: str, message: str):
    """macOS 알림."""
    script = (
        f'display notification "{message}" '
        f'with title "{title}"'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _run_suno_playwright(keyword: str, lyrics: str, style: str,
                         select: str, proj_dir: Path) -> list:
    """Playwright 기반 Suno 자동화 (기본 방식)."""
    from suno import SunoAutomation

    suno = SunoAutomation(download_dir=proj_dir, headless=False, max_retries=2)
    result = asyncio.run(suno.generate(
        title=keyword, prompt=lyrics, style=style,
        count=2, select=select,
    ))

    if not result.get("success"):
        raise RuntimeError(result.get("error", "Playwright 자동화 실패"))

    return result["downloaded_files"]


def _run_suno_pyautogui(keyword: str, lyrics: str, style: str,
                        api_key: str, select: str, proj_dir: Path) -> list:
    """pyautogui 좌표 기반 Suno 자동화 (fallback)."""
    sys.path.insert(0, str(Path(__file__).parent))
    from suno_runner import run as suno_run

    return suno_run(
        title=keyword, prompt=lyrics, style=style,
        api_key=api_key, select=select,
        output_dir=proj_dir, interactive=False,
    )


def run_project(project_id: str, config: dict):
    """단일 프로젝트의 전체 파이프라인 실행."""
    api_key = config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("❌ Anthropic API 키가 없습니다. 설정에서 API 키를 입력하세요.")
        sys.exit(1)

    projects_root = Path(config.get("projects_root", "~/SunoProjects")).expanduser()
    pm = ProjectManager(projects_root)

    project = pm.get_by_id(project_id)
    if not project:
        print(f"❌ 프로젝트를 찾을 수 없습니다: {project_id}")
        sys.exit(1)

    keyword   = project["keyword"]
    cover_abs = projects_root / project["cover_path"]
    proj_dir  = pm.project_dir(project_id)
    select    = config.get("default_select", "longest")
    vocal     = config.get("vocal_type", "female")
    base_style = config.get("default_style", "cinematic, orchestral, emotional")
    # 자동화 방식: playwright (기본) / pyautogui (fallback)
    automation = config.get("automation_mode", "playwright")

    pm.update_status(project_id, "processing")
    print(f"\n{'='*55}")
    print(f"프로젝트 시작: {project_id}")
    print(f"키워드: {keyword}")
    print(f"자동화: {automation}")
    print(f"{'='*55}\n")

    # ------------------------------------------------------------------
    # Step 1: 가사/스타일/설명 생성
    # ------------------------------------------------------------------
    # 성과 피드백 로드 (있으면)
    performance_hint = _load_performance_hint(projects_root)

    content_file = proj_dir / "content.json"
    if content_file.exists():
        print("[1/4] content.json 이미 존재 — 재사용")
        content = json.loads(content_file.read_text(encoding="utf-8"))
    else:
        print("[1/4] Claude Haiku로 가사/스타일/설명 생성 중...")
        content = generate_content_safe(
            keyword=keyword,
            image_path=str(cover_abs) if cover_abs.exists() else None,
            api_key=api_key,
            base_style=base_style,
            vocal=vocal,
            performance_hint=performance_hint,
        )
        content_file.write_text(
            json.dumps(content, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  가사: {content['lyrics'][:60]}...")
        print(f"  스타일: {content['style']}")

    lyrics = content.get("lyrics", keyword)
    style  = content.get("style", f"{base_style}, {vocal} vocal")

    # ------------------------------------------------------------------
    # Step 2: Suno 자동 조작 → MP3 다운로드
    # ------------------------------------------------------------------
    print("\n[2/4] Suno 자동 조작 시작...")
    mp3_files = None

    if automation == "playwright":
        # Playwright 기본 → 실패 시 pyautogui fallback
        try:
            mp3_files = _run_suno_playwright(keyword, lyrics, style, select, proj_dir)
        except Exception as e:
            print(f"  ⚠️ Playwright 실패: {e}")
            print("  pyautogui fallback 시도...")
            try:
                mp3_files = _run_suno_pyautogui(
                    keyword, lyrics, style, api_key, select, proj_dir
                )
            except Exception as e2:
                pm.update_status(project_id, "failed",
                                 error=f"Playwright+pyautogui 모두 실패: {e2}")
                print(f"❌ 자동화 실패: {e2}")
                return
    else:
        # pyautogui 직접 사용
        confirmed = _osascript_dialog(
            f"Chrome에서 https://suno.com/create 를 열고\\n"
            f"로그인 상태를 확인한 후 '확인'을 클릭하세요.\\n\\n"
            f"키워드: {keyword}",
            title="수노 자동화 — 준비 확인",
        )
        if not confirmed:
            print("사용자가 취소했습니다.")
            pm.update_status(project_id, "pending", error="사용자 취소")
            return
        try:
            mp3_files = _run_suno_pyautogui(
                keyword, lyrics, style, api_key, select, proj_dir
            )
        except Exception as e:
            pm.update_status(project_id, "failed", error=str(e))
            print(f"❌ Suno 자동화 오류: {e}")
            return

    if not mp3_files:
        pm.update_status(project_id, "failed", error="MP3 파일을 찾지 못함")
        print("❌ MP3 파일을 찾지 못했습니다.")
        return

    mp3_path = mp3_files[0]
    pm.update_status(project_id, "processing", mp3_path=str(mp3_path))
    print(f"  MP3: {mp3_path.name}")

    # ------------------------------------------------------------------
    # Step 3: MP3 + 커버이미지 → MP4
    # ------------------------------------------------------------------
    print("\n[3/4] FFmpeg로 영상 생성 중...")
    from media_processing import MediaProcessor

    processor = MediaProcessor(
        download_dir=proj_dir,
        output_dir=proj_dir,
    )
    cover_for_video = str(cover_abs) if cover_abs.exists() else None

    mp4_result = asyncio.run(
        processor.mp3_to_mp4(mp3_path.name, cover_image=cover_for_video)
    )

    if not mp4_result.get("success"):
        err = mp4_result.get("error", "알 수 없는 오류")
        pm.update_status(project_id, "failed", error=f"MP4 생성 실패: {err}")
        print(f"❌ MP4 생성 실패: {err}")
        return

    mp4_path = Path(mp4_result["output_path"])
    pm.update_status(project_id, "processing", mp4_path=str(mp4_path))
    print(f"  MP4: {mp4_path.name}")

    # ------------------------------------------------------------------
    # Step 4: YouTube 업로드
    # ------------------------------------------------------------------
    playlist_id = config.get("youtube_playlist_id", "")
    privacy     = config.get("youtube_privacy", "public")
    auto_upload = config.get("youtube_auto_upload", False)
    description = content.get("youtube_description", "")
    tags        = content.get("tags", ["AI music", "Suno"])

    if auto_upload:
        print("\n[4/4] YouTube 업로드 중...")
        from youtube_upload import YouTubeUploader

        uploader = YouTubeUploader()
        yt_result = asyncio.run(
            uploader.upload(
                video_path=str(mp4_path),
                title=keyword,
                description=description,
                tags=tags,
                playlist_id=playlist_id or None,
                privacy=privacy,
            )
        )

        if yt_result.get("success"):
            youtube_url = yt_result["video_url"]
            video_id = yt_result["video_id"]
            pm.update_status(project_id, "done", youtube_url=youtube_url)
            print(f"  ✅ 업로드 완료: {youtube_url}")
            _notify("수노 자동화 완료 ✅", f"{keyword}\n{youtube_url}")

            # 성과 추적용 기록 저장
            _save_upload_record(projects_root, project_id, {
                "video_id": video_id,
                "keyword": keyword,
                "style": style,
                "tags": tags,
                "uploaded_at": datetime.now().isoformat(),
            })
        else:
            err = yt_result.get("error", "알 수 없는 오류")
            pm.update_status(project_id, "failed", error=f"YouTube 업로드 실패: {err}")
            print(f"❌ YouTube 업로드 실패: {err}")
            return
    else:
        pm.update_status(project_id, "done")
        print("\n[4/4] YouTube 업로드 건너뜀 (설정에서 비활성화)")
        print(f"  MP4 위치: {mp4_path}")
        _notify("수노 자동화 완료 ✅", f"{keyword} — MP4 생성 완료")

    print(f"\n{'='*55}")
    print(f"✅ 프로젝트 완료: {project_id}")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="수노 파이프라인 실행")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project-id", help="실행할 프로젝트 ID")
    group.add_argument("--next",       action="store_true", help="큐에서 다음 대기 항목 처리")
    args = parser.parse_args()

    config = load_config()

    if args.next:
        projects_root = Path(config.get("projects_root", "~/SunoProjects")).expanduser()
        pm = ProjectManager(projects_root)
        pm.scan_input()  # input/ 폴더 스캔
        pending = pm.get_pending()
        if not pending:
            print("대기 중인 프로젝트가 없습니다.")
            sys.exit(0)
        project_id = pending[0]["id"]
        print(f"다음 프로젝트: {project_id}")
    else:
        project_id = args.project_id

    run_project(project_id, config)


if __name__ == "__main__":
    main()
