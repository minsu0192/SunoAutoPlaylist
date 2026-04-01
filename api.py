"""
SunoAutoPlaylist FastAPI 서버
React 웹앱에서 Python 자동화 모듈을 호출할 수 있는 REST API를 제공합니다.

실행: python api.py
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from suno import SunoAutomation
from media_processing import MediaProcessor
from playlist import PlaylistManager
from youtube_upload import YouTubeUploader

# ──────────────────────────────────────────
# 디렉터리 설정 (server.py와 동일)
# ──────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR   = BASE_DIR / "output"
DOWNLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────
# 앱 & CORS
# ──────────────────────────────────────────
app = FastAPI(title="SunoAutoPlaylist API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────
# Job 상태 관리 (인메모리 dict)
# 프로세스 재시작 시 초기화됨 — MVP 용도로 충분
# ──────────────────────────────────────────
jobs: dict[str, dict[str, Any]] = {}


def create_job(job_type: str) -> str:
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id":     job_id,
        "type":       job_type,
        "status":     "pending",   # pending | running | done | error
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "result":     None,
        "error":      None,
    }
    return job_id


def update_job(job_id: str, status: str, result=None, error=None, progress: dict = None):
    if job_id in jobs:
        update = {
            "status":     status,
            "updated_at": datetime.utcnow().isoformat(),
            "result":     result,
            "error":      error,
        }
        if progress is not None:
            update["progress"] = progress
        jobs[job_id].update(update)

# ──────────────────────────────────────────
# 요청 모델
# ──────────────────────────────────────────
class GenerateRequest(BaseModel):
    title: str
    prompt: str
    style: str = ""
    count: int = 2

class ConvertRequest(BaseModel):
    song_filename: str
    cover_image: Optional[str] = None

class PlaylistRequest(BaseModel):
    name: str
    songs: list[str] = []

class UploadRequest(BaseModel):
    video_path: str
    title: str
    description: str = ""
    tags: list[str] = []
    playlist_id: Optional[str] = None
    privacy: str = "public"

class PipelineRequest(BaseModel):
    title: str
    prompt: str
    style: str = ""
    yt_playlist: Optional[str] = None

class UiCheckRequest(BaseModel):
    force: bool = False

# ──────────────────────────────────────────
# 헬스체크 & 목록 조회
# ──────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/songs")
async def list_songs():
    mp3_files = sorted(DOWNLOAD_DIR.glob("*.mp3"))
    songs = [
        {"filename": f.name, "size_mb": round(f.stat().st_size / 1024 / 1024, 2)}
        for f in mp3_files
    ]
    return {"songs": songs, "total": len(songs)}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

# ──────────────────────────────────────────
# 수노 음악 생성
# ──────────────────────────────────────────
@app.post("/generate")
async def generate(req: GenerateRequest):
    job_id = create_job("generate")
    asyncio.create_task(_run_generate(job_id, req))
    return {"job_id": job_id}


async def _run_generate(job_id: str, req: GenerateRequest):
    update_job(job_id, "running")
    suno = SunoAutomation(download_dir=DOWNLOAD_DIR)
    result = await suno.generate(
        title=req.title,
        prompt=req.prompt,
        style=req.style,
        count=req.count,
    )
    if result.get("success"):
        update_job(job_id, "done", result=result)
    else:
        update_job(job_id, "error", error=result.get("error", "알 수 없는 오류"))

# ──────────────────────────────────────────
# MP3 → MP4 변환
# ──────────────────────────────────────────
@app.post("/convert")
async def convert(req: ConvertRequest):
    job_id = create_job("convert")
    asyncio.create_task(_run_convert(job_id, req))
    return {"job_id": job_id}


async def _run_convert(job_id: str, req: ConvertRequest):
    update_job(job_id, "running")
    processor = MediaProcessor(download_dir=DOWNLOAD_DIR, output_dir=OUTPUT_DIR)
    result = await processor.mp3_to_mp4(
        song_filename=req.song_filename,
        cover_image=req.cover_image,
    )
    if result.get("success"):
        update_job(job_id, "done", result=result)
    else:
        update_job(job_id, "error", error=result.get("error"))

# ──────────────────────────────────────────
# 플레이리스트 생성 (동기 함수 → executor)
# ──────────────────────────────────────────
@app.post("/playlist")
async def create_playlist(req: PlaylistRequest):
    job_id = create_job("playlist")
    asyncio.create_task(_run_playlist(job_id, req))
    return {"job_id": job_id}


async def _run_playlist(job_id: str, req: PlaylistRequest):
    update_job(job_id, "running")
    loop = asyncio.get_event_loop()
    manager = PlaylistManager(download_dir=DOWNLOAD_DIR)
    result = await loop.run_in_executor(
        None, manager.create_m3u, req.name, req.songs
    )
    if result.get("success"):
        update_job(job_id, "done", result=result)
    else:
        update_job(job_id, "error", error=result.get("error"))

# ──────────────────────────────────────────
# YouTube 업로드
# ──────────────────────────────────────────
@app.post("/upload")
async def upload(req: UploadRequest):
    job_id = create_job("upload")
    asyncio.create_task(_run_upload(job_id, req))
    return {"job_id": job_id}


async def _run_upload(job_id: str, req: UploadRequest):
    update_job(job_id, "running")
    uploader = YouTubeUploader()
    result = await uploader.upload(
        video_path=req.video_path,
        title=req.title,
        description=req.description,
        tags=req.tags,
        playlist_id=req.playlist_id,
        privacy=req.privacy,
    )
    if result.get("success"):
        update_job(job_id, "done", result=result)
    else:
        update_job(job_id, "error", error=result.get("error"))

# ──────────────────────────────────────────
# 전체 파이프라인 (생성 → 변환 → 업로드)
# ──────────────────────────────────────────
@app.post("/pipeline")
async def pipeline(req: PipelineRequest):
    job_id = create_job("pipeline")
    asyncio.create_task(_run_pipeline(job_id, req))
    return {"job_id": job_id}


async def _run_pipeline(job_id: str, req: PipelineRequest):
    update_job(job_id, "running")
    pipeline_result: dict[str, Any] = {}

    # 1단계: 수노 음악 생성
    suno = SunoAutomation(download_dir=DOWNLOAD_DIR)
    gen = await suno.generate(
        title=req.title,
        prompt=req.prompt,
        style=req.style,
        count=2,
    )
    pipeline_result["generation"] = gen
    if not gen.get("success"):
        update_job(job_id, "error", error=gen.get("error"), result=pipeline_result)
        return

    # 2단계: MP4 변환
    processor = MediaProcessor(download_dir=DOWNLOAD_DIR, output_dir=OUTPUT_DIR)
    mp4_results = []
    for song in gen.get("downloaded_files", []):
        mp4 = await processor.mp3_to_mp4(song_filename=song)
        mp4_results.append(mp4)
    pipeline_result["conversion"] = mp4_results

    # 3단계: YouTube 업로드
    uploader = YouTubeUploader()
    upload_results = []
    for mp4 in mp4_results:
        if mp4.get("success"):
            upload = await uploader.upload(
                video_path=mp4["output_path"],
                title=req.title,
                playlist_id=req.yt_playlist,
            )
            upload_results.append(upload)
    pipeline_result["uploads"] = upload_results

    update_job(job_id, "done", result=pipeline_result)

# ──────────────────────────────────────────
# UI 변경 감지
# ──────────────────────────────────────────
@app.post("/ui-check")
async def ui_check(
    req: UiCheckRequest,
    x_anthropic_api_key: Optional[str] = Header(default=None, alias="X-Anthropic-Api-Key"),
):
    job_id = create_job("ui_check")
    asyncio.create_task(_run_ui_check(job_id, req.force, x_anthropic_api_key))
    return {"job_id": job_id}


async def _run_ui_check(job_id: str, force: bool, api_key: Optional[str]):
    from suno_ui_checker import SunoUIChecker, STATE_FILE

    if force and STATE_FILE.exists():
        STATE_FILE.unlink()

    def on_progress(step: int, total: int, message: str, eta: float):
        pct = int(step / total * 100)
        update_job(job_id, "running", progress={"step": step, "total": total, "pct": pct, "message": message, "eta": eta})

    update_job(job_id, "running", progress={"step": 0, "total": 5, "pct": 0, "message": "수노의 UI 변경사항을 확인하는 중입니다...", "eta": 8.0})

    loop = asyncio.get_event_loop()
    checker = SunoUIChecker(api_key=api_key or "")
    report = await loop.run_in_executor(None, lambda: checker.run_check(progress_callback=on_progress))

    result = {
        "changed": report.changed,
        "changed_rois": report.changed_rois,
        "coords_updated": report.coords_updated,
        "tokens_used": report.tokens_used,
        "duration_sec": round(report.duration_sec, 2),
        "message": report.message,
    }
    update_job(job_id, "done", result=result)


@app.get("/ui-state")
async def get_ui_state():
    from suno_ui_checker import STATE_FILE, ACTIONS_FILE
    import json

    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    actions = {}
    if ACTIONS_FILE.exists():
        try:
            actions = json.loads(ACTIONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "last_checked": state.get("last_checked"),
        "check_stats": state.get("check_stats"),
        "has_coords": bool(actions),
        "coord_keys": list(actions.keys()),
    }


# ──────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
