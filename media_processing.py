"""
미디어 처리 모듈
FFmpeg를 사용해 MP3 + 커버이미지 → YouTube용 MP4를 만듭니다.
"""

import asyncio
from pathlib import Path
from typing import Optional

DEFAULT_COVER = Path(__file__).parent / "assets" / "default_cover.jpg"


class MediaProcessor:
    def __init__(self, download_dir: Path, output_dir: Path):
        self.download_dir = Path(download_dir)
        self.output_dir   = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    async def mp3_to_mp4(self, song_filename: str, cover_image: Optional[str] = None) -> dict:
        mp3_path = self.download_dir / song_filename
        if not mp3_path.exists():
            return {"success": False, "error": f"파일 없음: {song_filename}"}

        cover_path = Path(cover_image) if cover_image else DEFAULT_COVER
        if not cover_path.exists():
            cover_path = await self._create_default_cover(mp3_path.stem)

        output_filename = mp3_path.stem + ".mp4"
        output_path = self.output_dir / output_filename

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(cover_path),
            "-i", str(mp3_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            str(output_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            return {"success": False, "error": stderr.decode()[-500:]}

        return {
            "success": True,
            "input_mp3": song_filename,
            "output_path": str(output_path),
            "output_filename": output_filename,
        }

    async def _create_default_cover(self, title: str) -> Path:
        assets_dir = Path(__file__).parent / "assets"
        assets_dir.mkdir(exist_ok=True)
        cover_path = assets_dir / f"{title}_cover.jpg"

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=black:s=1920x1080:r=1",
            "-vf", f"drawtext=text='{title}':fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h-text_h)/2",
            "-frames:v", "1",
            str(cover_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return cover_path
