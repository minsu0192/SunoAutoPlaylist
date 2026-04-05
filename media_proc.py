"""
media_proc.py — 썸네일 생성 + FFmpeg으로 MP3 + 이미지 → MP4 변환

요구사항: ffmpeg이 PATH에 설치되어 있어야 한다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ── 폰트 경로 (macOS) ──
_FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_FONT_KOREAN = "/System/Library/Fonts/AppleSDGothicNeo.ttc"


def _crop_resize(img: Image.Image, width: int, height: int) -> Image.Image:
    """이미지를 width x height로 크롭 + 리사이즈"""
    img_ratio = img.width / img.height
    target_ratio = width / height
    if img_ratio > target_ratio:
        new_h = img.height
        new_w = int(new_h * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, new_h))
    else:
        new_w = img.width
        new_h = int(new_w / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, new_w, top + new_h))
    return img.resize((width, height), Image.LANCZOS)


def make_thumbnail(
    bg_image: Path,
    title: str,
    output_path: Path,
    channel_name: str = "Seoul Diary\nPlaylist",
    width: int = 1920,
    height: int = 1080,
) -> Path:
    """
    essential; 스타일 썸네일 생성.
    큰 볼드 채널명 중앙 + 점선 구분선 + 밝은 배경
    """
    img = Image.open(bg_image).convert("RGB")
    img = _crop_resize(img, width, height)

    # 살짝만 어둡게 (20% — 텍스트 가독성용)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 50))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")

    draw = ImageDraw.Draw(img)

    # 채널명 폰트 (essential; 스타일 — 큰 볼드)
    try:
        font_big = ImageFont.truetype(_FONT_BOLD, 90)
    except Exception:
        font_big = ImageFont.truetype(_FONT_KOREAN, 90)

    # 채널명 텍스트 (줄바꿈 지원)
    lines = channel_name.split("\n")
    line_height = 105
    total_text_h = line_height * len(lines)
    y_start = (height - total_text_h) // 2 - 15

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_big)
        line_w = bbox[2] - bbox[0]
        x = (width - line_w) // 2
        y = y_start + i * line_height
        # 텍스트 그림자 (가독성)
        draw.text((x + 3, y + 3), line, fill=(0, 0, 0, 80), font=font_big)
        draw.text((x, y), line, fill="white", font=font_big)

    # 점선 구분선 (essential; 스타일)
    dotline_y = y_start + total_text_h + 10
    dot_spacing = 8
    dot_width = 300
    dot_start_x = (width - dot_width) // 2
    for x in range(dot_start_x, dot_start_x + dot_width, dot_spacing):
        draw.rectangle([x, dotline_y, x + 3, dotline_y + 3], fill=(255, 255, 255, 200))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=95)
    return output_path


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
