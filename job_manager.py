"""
job_manager.py — 고객별 작업 관리 시스템

각 고객 주문 = 1개의 job
폴더: ~/SunoOutput/jobs/<job_id>/
상태: job.json
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

JOBS_DIR = Path.home() / "SunoOutput" / "jobs"


# ════════════════════════════════════════════════════════
# 작업 상태 정의
# ════════════════════════════════════════════════════════

# 진행 단계
STATUS_CREATED = "created"            # 생성됨, 음원 미생성
STATUS_SONGS_READY = "songs_ready"    # 음원 생성 완료, 고객 컨펌 대기
STATUS_SONGS_SELECTED = "songs_selected"  # 곡 선택 완료
STATUS_IMAGES_READY = "images_ready"  # 이미지 후보 준비, 고객 컨펌 대기
STATUS_IMAGE_SELECTED = "image_selected"  # 이미지 선택 완료
STATUS_VIDEO_READY = "video_ready"    # 최종 영상 완성
STATUS_DELIVERED = "delivered"        # 고객 전달 완료


@dataclass
class JobInfo:
    """job.json에 저장되는 작업 메타데이터"""
    job_id: str
    keyword: str
    language: str = "english"          # english/korean
    customer_name: str = ""            # 크몽 닉네임 등 (선택)
    customer_note: str = ""            # 고객 요구사항 메모
    tier: str = "T1"                   # T1/T2/T3/T4
    status: str = STATUS_CREATED
    created_at: str = ""
    updated_at: str = ""

    # 음원 정보
    songs: list[dict] = field(default_factory=list)  # [{file, title, duration, style}, ...]
    selected_song_indices: list[int] = field(default_factory=list)

    # 이미지 정보
    images: list[dict] = field(default_factory=list)  # [{file, photographer, photographer_url, image_url}, ...]
    selected_image_index: int = -1

    # 결과물
    thumbnail_path: str = ""
    video_path: str = ""

    # YouTube 정보
    yt_title: str = ""
    yt_description: str = ""
    yt_tags: list[str] = field(default_factory=list)

    def save(self, job_dir: Path) -> None:
        self.updated_at = datetime.now().isoformat()
        (job_dir / "job.json").write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, job_dir: Path) -> "JobInfo":
        data = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
        return cls(**data)


# ════════════════════════════════════════════════════════
# 작업 생성/조회
# ════════════════════════════════════════════════════════

def create_job(
    keyword: str,
    language: str = "english",
    customer_name: str = "",
    customer_note: str = "",
    tier: str = "T1",
) -> tuple[Path, JobInfo]:
    """새 작업 생성. (job_dir, job_info) 반환."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)

    # job_id: 타임스탬프 + 키워드
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = "".join(c if c.isalnum() or c in "-_가-힣" else "_" for c in keyword)[:20]
    job_id = f"{timestamp}_{safe_kw}"

    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "songs").mkdir(exist_ok=True)
    (job_dir / "images").mkdir(exist_ok=True)

    info = JobInfo(
        job_id=job_id,
        keyword=keyword,
        language=language,
        customer_name=customer_name,
        customer_note=customer_note,
        tier=tier,
        created_at=datetime.now().isoformat(),
    )
    info.save(job_dir)

    return job_dir, info


def get_job_dir(job_id: str) -> Path:
    """job_id로 디렉토리 경로 반환. 부분 매칭 지원."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    exact = JOBS_DIR / job_id
    if exact.exists():
        return exact
    # 부분 매칭 (suffix)
    for d in JOBS_DIR.iterdir():
        if d.is_dir() and job_id in d.name:
            return d
    raise FileNotFoundError(f"Job not found: {job_id}")


def list_jobs() -> list[JobInfo]:
    """모든 작업 목록 (최신순)."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []
    for d in sorted(JOBS_DIR.iterdir(), reverse=True):
        if d.is_dir() and (d / "job.json").exists():
            try:
                jobs.append(JobInfo.load(d))
            except Exception:
                pass
    return jobs


# ════════════════════════════════════════════════════════
# 미리듣기 HTML 생성
# ════════════════════════════════════════════════════════

def build_preview_html(job_dir: Path, info: JobInfo) -> Path:
    """
    음원 미리듣기 HTML 페이지 생성.
    고객에게 링크 보내거나 로컬에서 열어볼 수 있음.
    """
    songs_html = ""
    for i, song in enumerate(info.songs):
        fname = song["file"]
        title = song.get("title", f"Track {i+1}")
        duration = song.get("duration", 0)
        style = song.get("style", "")
        mins = int(duration // 60)
        secs = int(duration % 60)
        songs_html += f"""
        <div class="track">
            <div class="track-num">{i+1:02d}</div>
            <div class="track-info">
                <div class="track-title">{title}</div>
                <div class="track-meta">{mins}:{secs:02d} · {style}</div>
            </div>
            <audio controls preload="none" src="songs/{fname}"></audio>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{info.keyword} — 음원 미리듣기</title>
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        color: #fff;
        min-height: 100vh;
        padding: 40px 20px;
    }}
    .container {{ max-width: 720px; margin: 0 auto; }}
    .header {{
        text-align: center;
        margin-bottom: 40px;
        padding-bottom: 30px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }}
    .header h1 {{
        font-size: 32px;
        margin-bottom: 8px;
        background: linear-gradient(135deg, #a78bfa, #f0abfc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .header .meta {{ color: rgba(255,255,255,0.6); font-size: 14px; }}
    .track {{
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px;
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        margin-bottom: 12px;
        transition: background 0.2s;
    }}
    .track:hover {{ background: rgba(255,255,255,0.08); }}
    .track-num {{
        font-size: 24px;
        font-weight: bold;
        color: #a78bfa;
        min-width: 40px;
        text-align: center;
    }}
    .track-info {{ flex: 1; min-width: 0; }}
    .track-title {{
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .track-meta {{ font-size: 12px; color: rgba(255,255,255,0.5); }}
    audio {{ width: 280px; max-width: 100%; }}
    .footer {{
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid rgba(255,255,255,0.1);
        text-align: center;
        color: rgba(255,255,255,0.4);
        font-size: 12px;
    }}
    @media (max-width: 600px) {{
        .track {{ flex-wrap: wrap; }}
        audio {{ width: 100%; margin-top: 8px; }}
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{info.keyword}</h1>
        <div class="meta">{info.tier} · {len(info.songs)}곡 · {info.created_at[:10]}</div>
    </div>
    {songs_html}
    <div class="footer">
        Job ID: {info.job_id}<br>
        Generated by Seoul Diary Playlist
    </div>
</div>
</body>
</html>
"""
    out = job_dir / "preview.html"
    out.write_text(html, encoding="utf-8")
    return out


# ════════════════════════════════════════════════════════
# 곡/이미지 선택
# ════════════════════════════════════════════════════════

def select_songs(job_id: str, indices: list[int]) -> JobInfo:
    """고객이 선택한 곡 인덱스 저장 (1-based)."""
    job_dir = get_job_dir(job_id)
    info = JobInfo.load(job_dir)
    info.selected_song_indices = sorted(set(indices))
    info.status = STATUS_SONGS_SELECTED
    info.save(job_dir)
    return info


def select_image(job_id: str, index: int) -> JobInfo:
    """고객이 선택한 이미지 인덱스 저장 (1-based)."""
    job_dir = get_job_dir(job_id)
    info = JobInfo.load(job_dir)
    info.selected_image_index = index
    info.status = STATUS_IMAGE_SELECTED
    info.save(job_dir)
    return info


def get_selected_song_paths(job_id: str) -> list[Path]:
    """선택된 곡들의 Path 리스트 반환 (1-based 인덱스)."""
    job_dir = get_job_dir(job_id)
    info = JobInfo.load(job_dir)
    if not info.selected_song_indices:
        # 선택 안 했으면 모든 곡 반환
        return [job_dir / "songs" / s["file"] for s in info.songs]
    return [job_dir / "songs" / info.songs[i - 1]["file"]
            for i in info.selected_song_indices
            if 1 <= i <= len(info.songs)]


def get_selected_image_path(job_id: str) -> Optional[Path]:
    """선택된 이미지 Path 반환."""
    job_dir = get_job_dir(job_id)
    info = JobInfo.load(job_dir)
    if info.selected_image_index < 1 or info.selected_image_index > len(info.images):
        if info.images:
            return job_dir / "images" / info.images[0]["file"]
        return None
    return job_dir / "images" / info.images[info.selected_image_index - 1]["file"]


def delete_job(job_id: str) -> None:
    """작업 폴더 전체 삭제."""
    job_dir = get_job_dir(job_id)
    shutil.rmtree(job_dir)
