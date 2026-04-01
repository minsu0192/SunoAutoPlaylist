"""
Suno → YouTube 자동화 MCP 서버
Claude Desktop에서 이 서버를 연결하면 수노 음악 생성부터 유튜브 업로드까지 자동화됩니다.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

# MCP SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# 내부 모듈
from suno import SunoAutomation
from media_processing import MediaProcessor
from playlist import PlaylistManager
from youtube_upload import YouTubeUploader

# ──────────────────────────────────────────
# 설정
# ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR   = BASE_DIR / "output"
DOWNLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Server("suno-youtube-mcp")

# ──────────────────────────────────────────
# 툴 목록 정의
# ──────────────────────────────────────────
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_song",
            description="수노(Suno)에서 AI 음악을 생성하고 MP3로 다운로드합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title":  {"type": "string", "description": "곡 제목"},
                    "prompt": {"type": "string", "description": "음악 스타일/분위기 설명 (영어 권장)"},
                    "style":  {"type": "string", "description": "장르 태그 (예: K-pop, ballad, upbeat)"},
                    "count":  {"type": "integer", "description": "생성할 곡 수 (기본값: 2)", "default": 2},
                },
                "required": ["title", "prompt"],
            },
        ),
        Tool(
            name="list_songs",
            description="다운로드된 곡 목록을 보여줍니다.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="create_video",
            description="MP3 파일에 커버 이미지를 합쳐 YouTube용 MP4 영상을 만듭니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "song_filename": {"type": "string", "description": "변환할 MP3 파일명"},
                    "cover_image":   {"type": "string", "description": "커버 이미지 경로 (없으면 기본 이미지 사용)"},
                },
                "required": ["song_filename"],
            },
        ),
        Tool(
            name="create_playlist",
            description="다운로드된 곡들로 M3U 플레이리스트 파일을 생성합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name":  {"type": "string", "description": "플레이리스트 이름"},
                    "songs": {"type": "array", "items": {"type": "string"}, "description": "포함할 곡 파일명 목록 (비우면 전체)"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="upload_to_youtube",
            description="MP4 영상을 YouTube에 업로드합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "video_path":  {"type": "string", "description": "업로드할 MP4 파일 경로"},
                    "title":       {"type": "string", "description": "YouTube 영상 제목"},
                    "description": {"type": "string", "description": "영상 설명"},
                    "tags":        {"type": "array", "items": {"type": "string"}, "description": "태그 목록"},
                    "playlist_id": {"type": "string", "description": "추가할 YouTube 재생목록 ID (선택)"},
                    "privacy":     {"type": "string", "enum": ["public", "unlisted", "private"], "default": "public"},
                },
                "required": ["video_path", "title"],
            },
        ),
        Tool(
            name="full_pipeline",
            description="수노 곡 생성 → MP4 변환 → YouTube 업로드를 한 번에 실행합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title":       {"type": "string"},
                    "prompt":      {"type": "string"},
                    "style":       {"type": "string"},
                    "yt_playlist": {"type": "string", "description": "YouTube 재생목록 ID (선택)"},
                },
                "required": ["title", "prompt"],
            },
        ),
        Tool(
            name="check_ui_changes",
            description="수노 UI 변경사항을 감지하고 마우스 좌표를 자동 업데이트합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {"type": "boolean", "description": "캐시 무시하고 강제 재검사 (기본값: false)", "default": False},
                },
            },
        ),
        Tool(
            name="get_ui_status",
            description="마지막 UI 확인 시각과 감지 통계를 반환합니다.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]

# ──────────────────────────────────────────
# 툴 실행 핸들러
# ──────────────────────────────────────────
@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:

    if name == "generate_song":
        suno = SunoAutomation(download_dir=DOWNLOAD_DIR)
        result = await suno.generate(
            title=arguments["title"],
            prompt=arguments["prompt"],
            style=arguments.get("style", ""),
            count=arguments.get("count", 2),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "list_songs":
        mp3_files = list(DOWNLOAD_DIR.glob("*.mp3"))
        songs = [{"filename": f.name, "size_mb": round(f.stat().st_size / 1024 / 1024, 2)} for f in mp3_files]
        return [TextContent(type="text", text=json.dumps({"songs": songs, "total": len(songs)}, ensure_ascii=False, indent=2))]

    elif name == "create_video":
        processor = MediaProcessor(download_dir=DOWNLOAD_DIR, output_dir=OUTPUT_DIR)
        result = await processor.mp3_to_mp4(
            song_filename=arguments["song_filename"],
            cover_image=arguments.get("cover_image"),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "create_playlist":
        manager = PlaylistManager(download_dir=DOWNLOAD_DIR)
        result = manager.create_m3u(
            name=arguments["name"],
            songs=arguments.get("songs", []),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "upload_to_youtube":
        uploader = YouTubeUploader()
        result = await uploader.upload(
            video_path=arguments["video_path"],
            title=arguments["title"],
            description=arguments.get("description", ""),
            tags=arguments.get("tags", []),
            playlist_id=arguments.get("playlist_id"),
            privacy=arguments.get("privacy", "public"),
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "full_pipeline":
        results = {}

        # 1. 수노 생성
        suno = SunoAutomation(download_dir=DOWNLOAD_DIR)
        gen_result = await suno.generate(
            title=arguments["title"],
            prompt=arguments["prompt"],
            style=arguments.get("style", ""),
            count=2,
        )
        results["generation"] = gen_result

        # 2. MP4 변환
        processor = MediaProcessor(download_dir=DOWNLOAD_DIR, output_dir=OUTPUT_DIR)
        mp4_results = []
        for song in gen_result.get("downloaded_files", []):
            mp4 = await processor.mp3_to_mp4(song_filename=song)
            mp4_results.append(mp4)
        results["conversion"] = mp4_results

        # 3. YouTube 업로드
        uploader = YouTubeUploader()
        upload_results = []
        for mp4 in mp4_results:
            if mp4.get("success"):
                upload = await uploader.upload(
                    video_path=mp4["output_path"],
                    title=arguments["title"],
                    playlist_id=arguments.get("yt_playlist"),
                )
                upload_results.append(upload)
        results["uploads"] = upload_results

        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

    elif name == "check_ui_changes":
        from suno_ui_checker import SunoUIChecker, STATE_FILE
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        force = arguments.get("force", False)
        if force and STATE_FILE.exists():
            STATE_FILE.unlink()
        log = []
        def on_progress(step, total, message, eta):
            log.append(f"[{int(step/total*100)}%] {message}")
        checker = SunoUIChecker(api_key=api_key)
        loop = asyncio.get_event_loop()
        report = await loop.run_in_executor(None, lambda: checker.run_check(progress_callback=on_progress))
        result = {
            "changed": report.changed,
            "changed_rois": report.changed_rois,
            "coords_updated": report.coords_updated,
            "tokens_used": report.tokens_used,
            "duration_sec": round(report.duration_sec, 2),
            "message": report.message,
            "log": log,
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "get_ui_status":
        from suno_ui_checker import STATE_FILE, ACTIONS_FILE
        state, actions = {}, {}
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        if ACTIONS_FILE.exists():
            try:
                actions = json.loads(ACTIONS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        result = {
            "last_checked": state.get("last_checked"),
            "check_stats": state.get("check_stats"),
            "has_coords": bool(actions),
            "coord_keys": list(actions.keys()),
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return [TextContent(type="text", text=f"알 수 없는 툴: {name}")]

# ──────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
