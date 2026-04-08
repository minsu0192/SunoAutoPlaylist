"""
pipeline.py — 전체 파이프라인 오케스트레이터

scope: "songs" / "videos" / "upload"
"""

from __future__ import annotations

import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

from config import Config
from lyrics_gen import generate_song_content, generate_instrumental_description, generate_youtube_info, fetch_pixabay_image, fetch_unsplash_image, read_image_credit
from media_proc import make_video, make_thumbnail
import suno_bot
from suno_bot import load_actions, run_suno_session, run_suno_instrumental, setup_browser, _log
from yt_upload import YouTubeUploader

ProgressCallback = Callable[[str, int, int], None]


class Pipeline:

    def __init__(self, config: Config) -> None:
        self.config = config

    def run(
        self,
        item: dict,
        progress_callback: Optional[ProgressCallback] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        cfg = self.config
        keyword = item["keyword"]
        image_path = Path(item["image_path"]) if item.get("image_path") else None
        scope = cfg.pipeline_scope

        # 중단 플래그를 suno_bot에 전달
        suno_bot.stop_flag = stop_event

        # 이미지 없으면 Unsplash → Pixabay 순으로 자동 다운로드 시도
        if not image_path and scope in ("videos", "upload"):
            img_dir = Path(cfg.output_dir) / "images"

            # 1순위: Unsplash (시네마틱 고퀄)
            if cfg.unsplash_access_key:
                _log("[Unsplash] 배경 이미지 검색 중...")
                dl = fetch_unsplash_image(keyword, cfg.unsplash_access_key, img_dir)
                if dl:
                    image_path = dl
                    _log(f"[Unsplash] 이미지 다운로드 완료: {dl.name}")
                else:
                    _log("[Unsplash] 이미지를 찾지 못함")

            # 2순위: Pixabay fallback
            if not image_path and cfg.pixabay_api_key:
                _log("[Pixabay] fallback 이미지 검색 중...")
                dl = fetch_pixabay_image(keyword, cfg.pixabay_api_key, img_dir)
                if dl:
                    image_path = dl
                    _log(f"[Pixabay] 이미지 다운로드 완료: {dl.name}")
                else:
                    _log("[Pixabay] 이미지를 찾지 못함")

            if not image_path:
                _log("⚠️ 이미지 없음 → 곡 생성만 진행 (영상/업로드 생략)")
                scope = "songs"

        def _progress(step: str, current: int, total: int) -> None:
            if progress_callback:
                try:
                    progress_callback(step, current, total)
                except Exception:
                    pass

        def _check_stop():
            if stop_event and stop_event.is_set():
                raise RuntimeError("사용자에 의해 중단됨")

        total_steps = {"songs": 4, "videos": 5, "upload": 6}[scope]

        # ── [1] 검증 ─────────────────────────────────────────────
        _progress("검증 중...", 1, total_steps)
        self._validate(cfg, image_path)

        # vocal_pick이 both면 세션당 2곡, 아니면 세션당 1곡
        songs_per_vocal = 2 if cfg.vocal_pick == "both" else 1
        kr_sessions = math.ceil(cfg.korean_songs / songs_per_vocal) if cfg.korean_songs else 0
        en_sessions = math.ceil(cfg.english_songs / songs_per_vocal) if cfg.english_songs else 0
        # instrumental은 항상 2곡 사용
        inst_sessions = math.ceil(cfg.instrumental_songs / 2) if cfg.instrumental_songs else 0
        total_sessions = kr_sessions + en_sessions + inst_sessions

        # ── [2] 콘텐츠 생성 ───────────────────────────────────────
        _progress("가사/스타일 생성 중...", 2, total_steps)
        _check_stop()

        # 가사/스타일/설명을 병렬 생성 (Claude API 호출이 느리므로)
        sessions: list[dict] = [None] * (kr_sessions + en_sessions)
        inst_desc = ""
        yt_info = None

        def _gen_kr(i):
            c = generate_song_content(keyword, "korean", i, cfg.anthropic_api_key)
            return ("kr", i, c)

        def _gen_en(i):
            c = generate_song_content(keyword, "english", i, cfg.anthropic_api_key)
            return ("en", i, c)

        def _gen_inst():
            return generate_instrumental_description(keyword, cfg.anthropic_api_key)

        def _gen_yt():
            total_songs = cfg.korean_songs + cfg.english_songs + cfg.instrumental_songs
            return generate_youtube_info(keyword, total_songs, cfg.anthropic_api_key)

        # Instrumental 학습 체크
        if inst_sessions > 0:
            actions = load_actions()
            inst_required = ["simple_tab", "instrumental_toggle", "simple_create_btn"]
            inst_missing = [k for k in inst_required if k not in actions]
            if inst_missing:
                raise RuntimeError(f"Instrumental 학습 미완료: {inst_missing}")

        # 곡 생성은 순차 실행 (이전 제목을 프롬프트에 전달하여 중복 방지)
        used_titles: list[str] = []
        for i in range(kr_sessions):
            _check_stop()
            content = generate_song_content(keyword, "korean", i, cfg.anthropic_api_key, used_titles=used_titles)
            sessions[i] = content
            used_titles.append(content["title"])

        for i in range(en_sessions):
            _check_stop()
            content = generate_song_content(keyword, "english", i, cfg.anthropic_api_key, used_titles=used_titles)
            sessions[kr_sessions + i] = content
            used_titles.append(content["title"])

        # Instrumental 설명 + YouTube 정보는 곡과 독립이므로 병렬 생성
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = []
            if inst_sessions > 0:
                futures.append(pool.submit(_gen_inst))
            if scope == "upload":
                futures.append(pool.submit(_gen_yt))

            for fut in as_completed(futures):
                _check_stop()
                result = fut.result()
                if isinstance(result, str):
                    inst_desc = result
                elif isinstance(result, dict):
                    yt_info = result

        # None 제거 (혹시 빈 슬롯)
        sessions = [s for s in sessions if s is not None]

        # ── [3] Suno.com 자동화 ───────────────────────────────────
        _progress(f"Suno.com 준비 중... (총 {total_sessions}세션)", 3, total_steps)
        _check_stop()
        _log(f"=== Suno 자동화 시작 (한국어 {kr_sessions}세션 / 영어 {en_sessions}세션 / Inst {inst_sessions}세션) ===")
        _log(f"실행 범위: {scope} | vocal_pick: {cfg.vocal_pick}")
        setup_browser()

        all_mp3s: list[Path] = []
        kr_mp3s: list[Path] = []
        en_mp3s: list[Path] = []
        inst_mp3s: list[Path] = []
        current = 0

        # 한국어 세션
        kr_session_list = sessions[:kr_sessions]
        for idx, song_info in enumerate(kr_session_list):
            current += 1
            _progress(f"[세션 {current}/{total_sessions}] 한국어 새 곡 생성 중...", 3, total_steps)
            _log(f"=== 세션 {current}/{total_sessions}: 한국어 새 가사 — {song_info['title']} ===")
            _check_stop()
            try:
                mp3s = run_suno_session(
                    lyrics=song_info["lyrics"],
                    style=song_info["style"],
                    title=song_info["title"],
                    vocal_pick=cfg.vocal_pick,
                )
                kr_mp3s.extend(mp3s)
            except Exception as e:
                raise RuntimeError(f"한국어 세션 {idx + 1} 실패: {e}") from e

        # 영어 세션
        en_session_list = sessions[kr_sessions:]
        for idx, song_info in enumerate(en_session_list):
            current += 1
            _progress(f"[세션 {current}/{total_sessions}] 영어 새 곡 생성 중...", 3, total_steps)
            _log(f"=== 세션 {current}/{total_sessions}: 영어 새 가사 — {song_info['title']} ===")
            _check_stop()
            try:
                mp3s = run_suno_session(
                    lyrics=song_info["lyrics"],
                    style=song_info["style"],
                    title=song_info["title"],
                    vocal_pick=cfg.vocal_pick,
                )
                en_mp3s.extend(mp3s)
            except Exception as e:
                raise RuntimeError(f"영어 세션 {idx + 1} 실패: {e}") from e

        # 언어별 트리밍 (요청한 수만큼만)
        def _trim(mp3s: list[Path], want: int) -> list[Path]:
            if len(mp3s) > want > 0:
                for f in mp3s[want:]:
                    try: f.unlink()
                    except Exception: pass
                return mp3s[:want]
            return mp3s

        kr_mp3s = _trim(kr_mp3s, cfg.korean_songs)
        en_mp3s = _trim(en_mp3s, cfg.english_songs)
        vocal_mp3s = kr_mp3s + en_mp3s

        # Instrumental 세션
        for i in range(inst_sessions):
            current += 1
            _progress(f"Instrumental 세션 {current}/{total_sessions}...", 3, total_steps)
            _check_stop()
            try:
                mp3s = run_suno_instrumental(description=inst_desc)
                inst_mp3s.extend(mp3s)
            except Exception as e:
                raise RuntimeError(f"Instrumental 세션 {i + 1} 실패: {e}") from e

        # Instrumental 곡 수 트리밍
        if len(inst_mp3s) > cfg.instrumental_songs and cfg.instrumental_songs > 0:
            excess = inst_mp3s[cfg.instrumental_songs:]
            inst_mp3s = inst_mp3s[:cfg.instrumental_songs]
            for f in excess:
                try:
                    f.unlink()
                except Exception:
                    pass

        all_mp3s = vocal_mp3s + inst_mp3s

        if not all_mp3s:
            raise RuntimeError(
                "다운로드된 MP3 파일이 없습니다.\n"
                "1. Chrome에서 suno.com 로그인 확인\n"
                "2. UI 학습이 정확한지 확인\n"
                "3. 접근성 권한이 켜져있는지 확인"
            )

        # ── scope: songs → 여기서 끝 ──────────────────────────────
        _log(f"=== 곡 다운로드 완료: {len(all_mp3s)}곡 ===")
        if scope == "songs":
            _progress(f"완료! {len(all_mp3s)}곡 다운로드됨", total_steps, total_steps)
            return

        # ── [4] 썸네일 + 영상 생성 ────────────────────────────────
        _check_stop()
        output_base = Path(cfg.output_dir) / self._safe_dirname(keyword)
        output_base.mkdir(parents=True, exist_ok=True)

        # 썸네일 생성 (사용자 지정 텍스트 + 사이즈 프리셋)
        thumbnail_text = cfg.thumbnail_text or "Seoul Diary Playlist"
        thumbnail_size = cfg.thumbnail_size or "M"
        _log(f"=== 썸네일 생성: '{thumbnail_text}' (크기 {thumbnail_size}) ===")
        _progress("썸네일 생성 중...", 4, total_steps)
        thumb_path = output_base / "thumbnail.jpg"
        try:
            make_thumbnail(
                image_path, thumbnail_text, thumb_path,
                channel_name=thumbnail_text,
                size_preset=thumbnail_size,
            )
            _log(f"썸네일 완료: {thumb_path.name}")
            video_image = thumb_path
        except Exception as e:
            _log(f"썸네일 생성 실패, 원본 이미지 사용: {e}")
            video_image = image_path

        # 모든 곡을 합쳐서 1개 영상 생성
        _log(f"=== MP4 영상 생성 ({len(all_mp3s)}곡 → 1개 영상) ===")
        _progress(f"MP4 영상 생성 중... ({len(all_mp3s)}곡 합치기)", 4, total_steps)
        _check_stop()

        output_mp4 = output_base / f"{self._safe_filename(keyword)}.mp4"
        for mp3 in all_mp3s:
            _log(f"  곡: {mp3.name}")
        try:
            make_video(all_mp3s, video_image, output_mp4)
            _log(f"영상 완료: {output_mp4.name} ({output_mp4.stat().st_size / 1024 / 1024:.1f} MB)")
        except Exception as e:
            raise RuntimeError(f"영상 생성 실패: {e}") from e

        if scope == "videos":
            _progress(f"완료! 영상: {output_mp4}", total_steps, total_steps)
            return

        # ── [5] YouTube 업로드 ────────────────────────────────────
        if not cfg.youtube_client_secrets:
            _log("YouTube client_secrets 미설정 → 업로드 생략")
            _progress(f"완료 (YouTube 미설정). 영상: {output_base}", total_steps, total_steps)
            return

        _log("=== YouTube 업로드 시작 ===")
        _progress("YouTube 업로드 중...", 5, total_steps)
        _check_stop()
        if yt_info is None:
            yt_info = {"title": keyword, "description": keyword, "tags": [keyword]}
        uploader = YouTubeUploader()

        title = yt_info["title"]
        # 사진작가 크레딧을 설명에 자동 추가
        description = yt_info["description"]
        credit = read_image_credit(image_path)
        if credit:
            description = f"{description}\n\n{credit}"
            _log(f"크레딧 추가: {credit}")
        _log(f"YouTube 업로드: {title}")
        try:
            url = uploader.upload(
                video_path=output_mp4, title=title,
                description=description, tags=yt_info["tags"],
                playlist_id=cfg.youtube_playlist_id or "", privacy=cfg.youtube_privacy,
            )
            _log(f"업로드 완료: {url}")
            if cfg.youtube_playlist_id:
                _log(f"플레이리스트에 추가됨: {cfg.youtube_playlist_id}")
        except Exception as e:
            raise RuntimeError(f"YouTube 업로드 실패: {e}") from e

        _log(f"=== 전체 완료! ===")
        _progress(f"완료! {url}", total_steps, total_steps)

    def _validate(self, cfg: Config, image_path: Path | None) -> None:
        if not cfg.anthropic_api_key:
            raise ValueError("API 키가 없습니다.")
        if not (Path.home() / ".suno_actions.json").exists():
            raise ValueError("UI 학습을 먼저 완료하세요.")
        try:
            load_actions()
        except Exception as e:
            raise ValueError(f"UI 학습 파일 로드 실패: {e}") from e
        if image_path and not image_path.exists():
            raise ValueError(f"이미지 없음: {image_path}")
        if cfg.korean_songs + cfg.english_songs + cfg.instrumental_songs == 0:
            raise ValueError("곡 수가 0입니다.")

    @staticmethod
    def _safe_dirname(text: str) -> str:
        return "".join(c if c.isalnum() or c in " _-" else "_" for c in text).strip()[:50] or "untitled"

    @staticmethod
    def _safe_filename(text: str) -> str:
        return "".join(c if c.isalnum() or c in "_-" else "_" for c in text).strip()[:40] or "song"
