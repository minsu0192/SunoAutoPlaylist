"""
플레이리스트 관리 모듈
다운로드된 MP3 파일로 M3U 플레이리스트를 생성합니다.
"""

import json
from datetime import datetime
from pathlib import Path


class PlaylistManager:
    def __init__(self, download_dir: Path):
        self.download_dir = Path(download_dir)

    def create_m3u(self, name: str, songs: list[str] = []) -> dict:
        if not songs:
            mp3_files = sorted(self.download_dir.glob("*.mp3"))
        else:
            mp3_files = [self.download_dir / s for s in songs if (self.download_dir / s).exists()]

        if not mp3_files:
            return {"success": False, "error": "플레이리스트에 추가할 MP3 파일이 없습니다."}

        playlist_path = self.download_dir / f"{name}.m3u"
        lines = ["#EXTM3U", f"# 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}"]

        for mp3 in mp3_files:
            title = mp3.stem.replace("_", " ")
            lines.append(f"#EXTINF:-1,{title}")
            lines.append(str(mp3.resolve()))

        playlist_path.write_text("\n".join(lines), encoding="utf-8")

        meta = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "songs": [mp3.name for mp3 in mp3_files],
            "count": len(mp3_files),
            "playlist_file": str(playlist_path),
        }
        meta_path = self.download_dir / f"{name}_meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        return {"success": True, **meta}
