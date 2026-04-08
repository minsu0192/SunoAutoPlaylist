"""
media_proc.py — 썸네일 생성 + FFmpeg으로 MP3 + 이미지 → MP4 변환

요구사항: ffmpeg이 PATH에 설치되어 있어야 한다.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
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


# 사이즈 프리셋 (Bodoni 72 Bold 기준)
# M = "Seoul Diary Playlist" 같은 긴 텍스트용
# XL = "essential" / "playlist" 같은 짧은 단어용
THUMBNAIL_SIZE_PRESETS = {
    "M":  {"font_size": 170, "line_height": 105, "shadow": 3},
    "XL": {"font_size": 280, "line_height": 170, "shadow": 5},
}


def make_thumbnail(
    bg_image: Path,
    title: str,
    output_path: Path,
    channel_name: str = "Seoul Diary Playlist",
    width: int = 1920,
    height: int = 1080,
    size_preset: str = "M",
) -> Path:
    """
    essential; 스타일 썸네일 생성.
    배경 위에 channel_name 텍스트 (사이즈 프리셋: S/M/L/XL).
    """
    preset = THUMBNAIL_SIZE_PRESETS.get(size_preset, THUMBNAIL_SIZE_PRESETS["M"])
    font_size = preset["font_size"]
    line_height = preset["line_height"]
    shadow = preset["shadow"]

    img = Image.open(bg_image).convert("RGB")
    img = _crop_resize(img, width, height)

    # 살짝만 어둡게 (20% — 텍스트 가독성용)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 50))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")

    draw = ImageDraw.Draw(img)

    # 폰트 (Bodoni 72 Bold)
    _FONT_BODONI = "/System/Library/Fonts/Supplemental/Bodoni 72.ttc"
    try:
        font_big = ImageFont.truetype(_FONT_BODONI, font_size, index=1)
    except Exception:
        try:
            font_big = ImageFont.truetype(_FONT_BOLD, font_size)
        except Exception:
            font_big = ImageFont.truetype(_FONT_KOREAN, font_size)

    # 텍스트 (줄바꿈 지원) — 중앙보다 위쪽에 배치
    lines = channel_name.split("\n")
    total_text_h = line_height * len(lines)
    y_start = (height - total_text_h) // 2 - 110

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_big)
        line_w = bbox[2] - bbox[0]
        x = (width - line_w) // 2
        y = y_start + i * line_height
        # 텍스트 그림자
        draw.text((x + shadow, y + shadow), line, fill=(0, 0, 0, 80), font=font_big)
        draw.text((x, y), line, fill="white", font=font_big)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=95)
    return output_path


def get_audio_duration(mp3_path: Path) -> float:
    """ffprobe로 mp3 파일 길이(초) 측정. 실패 시 0.0."""
    ffmpeg = _check_ffmpeg()
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    if not Path(ffprobe).exists():
        ffprobe = shutil.which("ffprobe") or "ffprobe"
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def build_tracklist(tracks: list[tuple[Path, str]]) -> str:
    """
    YouTube 자동 챕터용 트랙리스트 생성.
    YouTube 요구사항:
    - 첫 줄은 반드시 00:00
    - 최소 3개 타임스탬프
    - 각 챕터 최소 10초
    - 시간 오름차순

    Format:
        00:00 Track 1
        02:33 Track 2
        ...
    """
    if not tracks:
        return ""

    lines = []
    cumulative = 0.0
    for mp3, title in tracks:
        # 분:초 또는 시:분:초 포맷
        total_sec = int(cumulative)
        if total_sec >= 3600:
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            s = total_sec % 60
            ts = f"{h}:{m:02d}:{s:02d}"
        else:
            m = total_sec // 60
            s = total_sec % 60
            ts = f"{m:02d}:{s:02d}"
        lines.append(f"{ts} {title}")

        # 다음 트랙 시작 시각 = 이전 누적 + 이 트랙 길이
        duration = get_audio_duration(mp3)
        cumulative += duration

    return "\n".join(lines)


def _check_ffmpeg() -> str:
    """ffmpeg 실행 파일 경로를 반환한다. 없으면 RuntimeError."""
    # .app 번들에서는 PATH에 /opt/homebrew/bin이 없을 수 있으므로 직접 탐색
    candidates = [
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    raise RuntimeError(
        "ffmpeg을 찾을 수 없습니다.\n"
        "설치 방법: brew install ffmpeg"
    )


def make_video(mp3_paths: list[Path] | Path, image_path: Path, output_path: Path) -> Path:
    """
    이미지 + MP3 여러 곡을 합쳐 1개 MP4 영상을 만든다.
    곡들을 순서대로 이어붙여 하나의 영상으로 생성.
    """
    ffmpeg = _check_ffmpeg()

    # 단일 Path도 리스트로 변환
    if isinstance(mp3_paths, Path):
        mp3_paths = [mp3_paths]

    for mp3 in mp3_paths:
        if not mp3.exists():
            raise FileNotFoundError(f"MP3 파일이 없습니다: {mp3}")
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일이 없습니다: {image_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 여러 곡이면 먼저 하나로 합치기
    if len(mp3_paths) == 1:
        combined_mp3 = mp3_paths[0]
    else:
        # ffmpeg concat으로 MP3 합치기
        # 파일명에 apostrophe 등 특수문자가 있으면 concat list 구문이 깨지므로
        # 번호 symlink로 안전한 경로를 만들어 사용한다.
        concat_list = output_path.parent / "_concat_list.txt"
        combined_mp3 = output_path.parent / "_combined.mp3"

        with tempfile.TemporaryDirectory() as tmpdir:
            for i, mp3 in enumerate(mp3_paths):
                link = Path(tmpdir) / f"{i:04d}.mp3"
                link.symlink_to(mp3.resolve())

            with concat_list.open("w", encoding="utf-8") as f:
                for i in range(len(mp3_paths)):
                    f.write(f"file '{tmpdir}/{i:04d}.mp3'\n")

            concat_cmd = [
                ffmpeg, "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy", str(combined_mp3),
            ]
            try:
                r = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=120)
                if r.returncode != 0:
                    raise RuntimeError(f"MP3 합치기 실패:\n{r.stderr[-1000:]}")
            except subprocess.TimeoutExpired as e:
                raise RuntimeError("MP3 합치기 타임아웃") from e

    # 이미지 + 합쳐진 오디오 → MP4
    cmd = [
        ffmpeg, "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(combined_mp3),
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", "ultrafast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("ffmpeg 변환 타임아웃 (10분 초과)") from e

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 변환 실패:\n{result.stderr[-2000:]}")

    if not output_path.exists():
        raise RuntimeError(f"출력 파일 없음: {output_path}")

    # 임시 파일 정리
    for tmp in [output_path.parent / "_concat_list.txt", output_path.parent / "_combined.mp3"]:
        if tmp.exists():
            tmp.unlink()

    return output_path
