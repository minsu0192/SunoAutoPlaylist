"""
queue_manager.py — 작업 큐 관리

큐 파일 위치: ~/.suno_queue.json
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUEUE_FILE = Path.home() / ".suno_queue.json"

# 허용 상태값
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

VALID_STATUSES = {STATUS_PENDING, STATUS_PROCESSING, STATUS_DONE, STATUS_FAILED}


class QueueManager:
    """JSON 파일 기반의 간단한 작업 큐."""

    def __init__(self) -> None:
        self._file = QUEUE_FILE
        self._items: list[dict] = []
        self._load()

    # ------------------------------------------------------------------ #
    # 내부 헬퍼                                                            #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        """디스크에서 큐를 로드한다."""
        if self._file.exists():
            try:
                with self._file.open("r", encoding="utf-8") as f:
                    self._items = json.load(f)
            except Exception:
                self._items = []
        else:
            self._items = []

    def _save(self) -> None:
        """현재 큐를 디스크에 저장한다."""
        try:
            with self._file.open("w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise RuntimeError(f"큐 저장 실패: {e}") from e

    # ------------------------------------------------------------------ #
    # 공개 API                                                             #
    # ------------------------------------------------------------------ #

    def add(self, keyword: str, image_path: str = "") -> str:
        """큐에 새 항목을 추가하고 항목 ID를 반환한다. image_path는 선택."""
        item_id = str(uuid.uuid4())
        item = {
            "id": item_id,
            "image_path": str(image_path) if image_path else "",
            "keyword": keyword,
            "status": STATUS_PENDING,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
        self._items.append(item)
        self._save()
        return item_id

    def get_all(self) -> list[dict]:
        """모든 큐 항목을 반환한다."""
        self._load()
        return list(self._items)

    def get_pending(self) -> list[dict]:
        """status가 pending인 항목만 반환한다."""
        self._load()
        return [item for item in self._items if item["status"] == STATUS_PENDING]

    def update_status(self, item_id: str, status: str, **kwargs: Any) -> None:
        """항목의 상태 및 추가 필드를 업데이트한다."""
        if status not in VALID_STATUSES:
            raise ValueError(f"유효하지 않은 상태: {status}. 허용값: {VALID_STATUSES}")
        self._load()
        for item in self._items:
            if item["id"] == item_id:
                item["status"] = status
                for key, value in kwargs.items():
                    item[key] = value
                self._save()
                return
        raise KeyError(f"ID '{item_id}'에 해당하는 항목이 없습니다.")

    def remove(self, item_id: str) -> None:
        """항목을 큐에서 제거한다."""
        self._load()
        before = len(self._items)
        self._items = [item for item in self._items if item["id"] != item_id]
        if len(self._items) == before:
            raise KeyError(f"ID '{item_id}'에 해당하는 항목이 없습니다.")
        self._save()

    def get_by_id(self, item_id: str) -> dict | None:
        """ID로 항목을 조회한다."""
        self._load()
        for item in self._items:
            if item["id"] == item_id:
                return dict(item)
        return None
