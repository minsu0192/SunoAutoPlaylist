"""
media_proc.py — FFmpeg으로 MP3 + 이미지 → MP4 변환

요구사항: ffmpeg이 PATH에 설치되어 있어야 한다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _check_ffmpeg() -> str:
    """ffmpeg 실행 파일 경로를 반환한다. 없으면 RuntimeError."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError(
            "ffmpeg을 찾을 수 없습니다.\n"
            "설치 방법: brew install ffmpeg"
        )
    return ffmpeg_path


def make_video(mp3_path: Path, image_path: Path, output_path: Path) -> Path:
    """
    이미지와 MP3를 합쳐 MP4 영상을 만든다.

    변환 규격:
    - 영상: 1920x1080 letterbox (검정 배경)
    - 오디오: MP3 → AAC 재인코딩
    - 컨테이너: MP4 (H.264 + AAC)

    Args:
        mp3_path:    입력 MP3 파일 경로
        image_path:  입력 이미지 파일 경로
        output_path: 출력 MP4 파일 경로

    Returns:
        output_path

    Raises:
        FileNotFoundError: 입력 파일 없음
        RuntimeError: ffmpeg 없음 또는 변환 실패
    """
    ffmpeg = _check_ffmpeg()

    if not mp3_path.exists():
        raise FileNotFoundError(f"MP3 파일이 없습니다: {mp3_path}")
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일이 없습니다: {image_path}")

    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # FFmpeg 명령 구성
    # -loop 1: 이미지를 정지 영상으로 반복
    # -i image: 이미지 입력
    # -i mp3: 오디오 입력
    # vf scale: 1920x1080 패드 (letterbox)
    # -shortest: 오디오 길이에 맞춰 자르기
    # -movflags +faststart: 스트리밍 최적화
    cmd = [
        ffmpeg,
        "-y",                         # 덮어쓰기 허용
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(mp3_path),
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10분 타임아웃
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("ffmpeg 변환 타임아웃 (10분 초과)") from e

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 변환 실패 (코드 {result.returncode}):\n"
            f"{result.stderr[-2000:]}"  # 마지막 2000자만
        )

    if not output_path.exists():
        raise RuntimeError(f"ffmpeg 실행 후 출력 파일이 없습니다: {output_path}")

    return output_path
