"""
config.py — 앱 설정 관리

설정 파일 위치: ~/.suno_auto.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

CONFIG_FILE = Path.home() / ".suno_auto.json"


@dataclass
class Config:
    anthropic_api_key: str = ""
    pixabay_api_key: str = ""
    korean_songs: int = 3
    english_songs: int = 3
    instrumental_songs: int = 0
    vocal_pick: str = "longer"  # "longer", "shorter", "random", "both"
    pipeline_scope: str = "songs"  # "songs", "videos", "upload"
    youtube_client_secrets: str = ""
    youtube_playlist_id: str = ""
    youtube_privacy: str = "public"
    output_dir: str = str(Path.home() / "SunoOutput")

    # ------------------------------------------------------------------ #
    # 클래스 메서드                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls) -> "Config":
        """~/.suno_auto.json 에서 설정을 로드한다.
        파일이 없으면 기본값으로 생성하고 저장한다."""
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                # 알 수 없는 키 무시, 누락된 키는 기본값 사용
                valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in valid_fields}
                return cls(**filtered)
            except Exception as e:
                print(f"[config] 설정 로드 실패, 기본값 사용: {e}")
                return cls()
        else:
            cfg = cls()
            cfg.save()
            return cfg

    # ------------------------------------------------------------------ #
    # 인스턴스 메서드                                                       #
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """~/.suno_auto.json 에 설정을 저장한다."""
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise RuntimeError(f"설정 저장 실패: {e}") from e

    def validate(self) -> list[str]:
        """설정 유효성 검사. 문제 있는 항목 메시지 목록 반환."""
        errors: list[str] = []
        if not self.anthropic_api_key:
            errors.append("Anthropic API 키가 설정되지 않았습니다.")
        if self.korean_songs < 0:
            errors.append("한국어 곡 수는 0 이상이어야 합니다.")
        if self.english_songs < 0:
            errors.append("영어 곡 수는 0 이상이어야 합니다.")
        if self.instrumental_songs < 0:
            errors.append("Instrumental 곡 수는 0 이상이어야 합니다.")
        if self.korean_songs + self.english_songs + self.instrumental_songs == 0:
            errors.append("전체 곡 수의 합은 1 이상이어야 합니다.")
        if self.youtube_privacy not in ("public", "unlisted", "private"):
            errors.append("YouTube 공개범위는 public/unlisted/private 중 하나여야 합니다.")
        return errors
