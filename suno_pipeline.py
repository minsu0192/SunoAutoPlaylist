"""
수노 자동화 파이프라인 오케스트레이터
단일 프로젝트를 처음부터 끝까지 처리:
  1. Claude Haiku: 키워드+이미지 → 가사/스타일/설명 생성
  2. pyautogui:    Suno 자동 조작 → MP3 다운로드
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
from pathlib import Path

from suno_lyrics_gen import generate_content_safe
from suno_project_manager import ProjectManager


CONFIG_FILE = Path.home() / ".suno_config.json"


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

    pm.update_status(project_id, "processing")
    print(f"\n{'='*55}")
    print(f"프로젝트 시작: {project_id}")
    print(f"키워드: {keyword}")
    print(f"{'='*55}\n")

    # ------------------------------------------------------------------
    # Step 1: 가사/스타일/설명 생성
    # ------------------------------------------------------------------
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
    # Chrome 준비 확인 (macOS 다이얼로그)
    confirmed = _osascript_dialog(
        f"Chrome에서 https://suno.com/create 를 열고\\n"
        f"로그인 상태를 확인한 후 '확인'을 클릭하세요.\\n\\n"
        f"키워드: {keyword}",
        title="수노 자동화 — 준비 확인",
    )
    if not confirmed:
        print("사용자가 취소했습니다.")
        pm.update_status(project_id, "pending", error="사용자 취소")
        sys.exit(0)

    print("\n[2/4] Suno 자동 조작 시작...")

    # suno_runner를 직접 import해서 호출 (같은 프로세스)
    sys.path.insert(0, str(Path(__file__).parent))
    from suno_runner import run as suno_run

    try:
        mp3_files = suno_run(
            title=keyword,
            prompt=lyrics,
            style=style,
            api_key=api_key,
            select=select,
            output_dir=proj_dir,
            interactive=False,
        )
    except SystemExit:
        pm.update_status(project_id, "failed", error="Suno 자동화 실패 (학습 필요)")
        sys.exit(1)
    except Exception as e:
        pm.update_status(project_id, "failed", error=str(e))
        print(f"❌ Suno 자동화 오류: {e}")
        sys.exit(1)

    if not mp3_files:
        pm.update_status(project_id, "failed", error="MP3 파일을 찾지 못함")
        print("❌ MP3 파일을 찾지 못했습니다.")
        sys.exit(1)

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
        sys.exit(1)

    mp4_path = Path(mp4_result["output_path"])
    pm.update_status(project_id, "processing", mp4_path=str(mp4_path))
    print(f"  MP4: {mp4_path.name}")

    # ------------------------------------------------------------------
    # Step 4: YouTube 업로드
    # ------------------------------------------------------------------
    playlist_id = config.get("youtube_playlist_id", "")
    privacy     = config.get("youtube_privacy", "public")
    auto_upload = config.get("youtube_auto_upload", False)
    description = content.get("description", "")
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
            pm.update_status(project_id, "done", youtube_url=youtube_url)
            print(f"  ✅ 업로드 완료: {youtube_url}")
            _notify("수노 자동화 완료 ✅", f"{keyword}\n{youtube_url}")
        else:
            err = yt_result.get("error", "알 수 없는 오류")
            pm.update_status(project_id, "failed", error=f"YouTube 업로드 실패: {err}")
            print(f"❌ YouTube 업로드 실패: {err}")
            sys.exit(1)
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
