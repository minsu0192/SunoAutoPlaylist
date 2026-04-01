"""
프로젝트 큐 관리 모듈
~/SunoProjects/input/ 폴더를 감시하고 queue.json 상태를 관리.

queue.json 구조:
[
  {
    "id":         "2026-04-01_sunset_calm",
    "keyword":    "sunset calm",
    "cover_path": "projects/2026-04-01_sunset_calm/cover.jpg",
    "status":     "pending",      # pending | processing | done | failed
    "created_at": "2026-04-01T12:00:00",
    "updated_at": "2026-04-01T12:05:00",
    "youtube_url": null,
    "error": null
  }
]
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path


class ProjectManager:
    IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, projects_root: Path):
        self.root = Path(projects_root).expanduser()
        self.input_dir = self.root / "input"
        self.projects_dir = self.root / "projects"
        self.queue_file = self.root / "queue.json"

        self.root.mkdir(parents=True, exist_ok=True)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # queue.json 읽기 / 쓰기
    # ------------------------------------------------------------------
    def _load_queue(self) -> list:
        if not self.queue_file.exists():
            return []
        try:
            return json.loads(self.queue_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_queue(self, queue: list):
        self.queue_file.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 파일명 → 키워드 변환
    # ------------------------------------------------------------------
    @staticmethod
    def filename_to_keyword(filename: str) -> str:
        """
        "01_sunset_calm.jpg" → "sunset calm"
        "rainy morning.jpg"  → "rainy morning"
        "003 - 도시의 밤.png" → "도시의 밤"
        """
        stem = Path(filename).stem
        # 앞쪽 숫자 + 구분자 제거: "01_", "003 - ", "1. " 등
        stem = re.sub(r"^\d+[\s\-_\.]+", "", stem)
        # 언더스코어 → 공백
        stem = stem.replace("_", " ").strip()
        return stem

    # ------------------------------------------------------------------
    # input/ 폴더 스캔 → 새 이미지를 queue에 추가
    # ------------------------------------------------------------------
    def scan_input(self) -> list:
        """input/ 폴더의 새 이미지를 감지해 queue에 추가. 추가된 항목 반환."""
        queue = self._load_queue()
        existing_ids = {item["id"] for item in queue}
        added = []

        images = sorted(
            [f for f in self.input_dir.iterdir()
             if f.is_file() and f.suffix.lower() in self.IMAGE_SUFFIXES],
            key=lambda f: f.stat().st_mtime,
        )

        for img in images:
            keyword = self.filename_to_keyword(img.name)
            date_str = datetime.now().strftime("%Y-%m-%d")
            safe_kw = re.sub(r'[\\/:*?"<>|]', "_", keyword)[:40].replace(" ", "_")
            project_id = f"{date_str}_{safe_kw}"

            # 이미 큐에 있으면 건너뜀
            if project_id in existing_ids:
                continue

            # projects/{id}/ 폴더 생성 + 이미지 복사
            project_dir = self.projects_dir / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            cover_dst = project_dir / "cover.jpg"
            shutil.copy2(str(img), str(cover_dst))

            # input/ 에서 이미지 제거 (처리 완료 표시)
            img.unlink()

            item = {
                "id": project_id,
                "keyword": keyword,
                "cover_path": str(cover_dst.relative_to(self.root)),
                "status": "pending",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "youtube_url": None,
                "error": None,
            }
            queue.append(item)
            existing_ids.add(project_id)
            added.append(item)
            print(f"[ProjectManager] 새 프로젝트 추가: {project_id} ('{keyword}')")

        if added:
            self._save_queue(queue)
        return added

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------
    def get_pending(self) -> list:
        return [i for i in self._load_queue() if i["status"] == "pending"]

    def get_all(self) -> list:
        return self._load_queue()

    def get_by_id(self, project_id: str) -> dict | None:
        for item in self._load_queue():
            if item["id"] == project_id:
                return item
        return None

    def get_stats(self) -> dict:
        queue = self._load_queue()
        stats = {"pending": 0, "processing": 0, "done": 0, "failed": 0}
        for item in queue:
            s = item.get("status", "pending")
            if s in stats:
                stats[s] += 1
        return stats

    # ------------------------------------------------------------------
    # 상태 업데이트
    # ------------------------------------------------------------------
    def update_status(self, project_id: str, status: str, **kwargs):
        """
        status: pending | processing | done | failed
        kwargs: youtube_url, error, mp3_path, mp4_path 등
        """
        queue = self._load_queue()
        for item in queue:
            if item["id"] == project_id:
                item["status"] = status
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                item.update(kwargs)
                break
        self._save_queue(queue)

    # ------------------------------------------------------------------
    # 프로젝트 폴더 경로
    # ------------------------------------------------------------------
    def project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id
