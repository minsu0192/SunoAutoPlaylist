#!/usr/bin/env python3
"""
suno_job.py — Job 관리 CLI

사용법:
    suno_job create <키워드> [--lang en|ko] [--tier T1|T2|T3|T4] [--customer 닉네임]
    suno_job list
    suno_job show <job-id>
    suno_job preview <job-id>                  # preview.html 열기
    suno_job select-songs <job-id> 1,3,5
    suno_job fetch-images <job-id> [--count 5]
    suno_job select-image <job-id> 3
    suno_job make-video <job-id>
    suno_job make-thumbnail <job-id> [--text "Seoul Diary Playlist"] [--size M|XL]
    suno_job upload <job-id>                   # YouTube 업로드
    suno_job delete <job-id>

JSON 출력: --json 플래그 추가 (다른 AI/스크립트 연동용)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))
from config import Config
from job_manager import (
    JOBS_DIR, JobInfo, STATUS_CREATED, STATUS_SONGS_READY,
    STATUS_SONGS_SELECTED, STATUS_IMAGES_READY, STATUS_IMAGE_SELECTED,
    STATUS_VIDEO_READY, STATUS_DELIVERED,
    create_job, get_job_dir, list_jobs, build_preview_html,
    select_songs, select_image, get_selected_song_paths, get_selected_image_path,
    delete_job,
)


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ════════════════════════════════════════════════════════
# CREATE — 새 작업 + 음원 생성
# ════════════════════════════════════════════════════════

def cmd_create(args):
    """새 작업 생성. 음원은 Suno 자동화 없이 수동 추가 또는 별도 명령."""
    job_dir, info = create_job(
        keyword=args.keyword,
        language=args.lang,
        customer_name=args.customer or "",
        customer_note=args.note or "",
        tier=args.tier,
    )
    print(f"✅ Job 생성: {info.job_id}")
    print(f"   폴더: {job_dir}")
    print(f"   다음 단계: songs/ 폴더에 mp3 추가 후 'suno_job index <job-id>' 실행")
    if args.json:
        _print_json({"job_id": info.job_id, "job_dir": str(job_dir)})


# ════════════════════════════════════════════════════════
# INDEX — songs/ 폴더의 mp3 파일을 job.json에 등록
# ════════════════════════════════════════════════════════

def cmd_index(args):
    """songs/ 폴더의 mp3 파일들을 스캔해서 job.json에 등록."""
    from media_proc import get_audio_duration

    job_dir = get_job_dir(args.job_id)
    info = JobInfo.load(job_dir)
    songs_dir = job_dir / "songs"

    songs = []
    for f in sorted(songs_dir.glob("*.mp3")):
        duration = get_audio_duration(f)
        songs.append({
            "file": f.name,
            "title": f.stem,
            "duration": round(duration, 1),
            "style": "",
        })

    info.songs = songs
    info.status = STATUS_SONGS_READY if songs else STATUS_CREATED
    info.save(job_dir)

    print(f"✅ {len(songs)}곡 인덱싱 완료")
    for i, s in enumerate(songs):
        m, sec = int(s["duration"] // 60), int(s["duration"] % 60)
        print(f"   {i+1:2d}. {s['title']} ({m}:{sec:02d})")
    if args.json:
        _print_json({"job_id": info.job_id, "songs": songs})


# ════════════════════════════════════════════════════════
# GENERATE-LYRICS — Claude로 가사/스타일 생성
# ════════════════════════════════════════════════════════

def cmd_gen_lyrics(args):
    """가사/스타일/제목 생성 (Suno에 입력용)."""
    from lyrics_gen import generate_song_content

    cfg = Config.load()
    job_dir = get_job_dir(args.job_id)
    info = JobInfo.load(job_dir)

    used_titles = []
    lyrics_dir = job_dir / "lyrics"
    lyrics_dir.mkdir(exist_ok=True)

    for i in range(args.count):
        content = generate_song_content(
            keyword=info.keyword,
            language=info.language,
            index=i,
            api_key=cfg.anthropic_api_key,
            used_titles=used_titles,
        )
        used_titles.append(content["title"])
        out = lyrics_dir / f"{i+1:02d}_{content['title'][:30].replace('/', '_')}.json"
        out.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ {i+1}. {content['title']}")
        print(f"   스타일: {content['style']}")

    print(f"\n📂 {lyrics_dir}")
    if args.json:
        _print_json({"job_id": info.job_id, "count": args.count, "lyrics_dir": str(lyrics_dir)})


# ════════════════════════════════════════════════════════
# LIST / SHOW
# ════════════════════════════════════════════════════════

def cmd_list(args):
    """모든 작업 목록."""
    jobs = list_jobs()
    if args.json:
        _print_json({"jobs": [{"job_id": j.job_id, "keyword": j.keyword,
                               "tier": j.tier, "status": j.status,
                               "songs": len(j.songs), "images": len(j.images)}
                              for j in jobs]})
        return

    if not jobs:
        print("작업 없음")
        return

    print(f"{'STATUS':<18} {'TIER':<5} {'JOB_ID':<35} {'KEYWORD':<20} {'곡':>4} {'이미지':>4}")
    print("-" * 90)
    for j in jobs:
        print(f"{j.status:<18} {j.tier:<5} {j.job_id:<35} {j.keyword[:18]:<20} {len(j.songs):>4} {len(j.images):>4}")


def cmd_show(args):
    """작업 상세 정보."""
    job_dir = get_job_dir(args.job_id)
    info = JobInfo.load(job_dir)

    if args.json:
        from dataclasses import asdict
        _print_json(asdict(info))
        return

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {info.job_id}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  키워드:   {info.keyword}")
    print(f"  티어:     {info.tier}")
    print(f"  상태:     {info.status}")
    print(f"  고객:     {info.customer_name or '-'}")
    print(f"  메모:     {info.customer_note or '-'}")
    print(f"  생성:     {info.created_at}")
    print(f"  수정:     {info.updated_at}")
    print(f"  폴더:     {job_dir}")

    if info.songs:
        print(f"\n  음원 ({len(info.songs)}곡):")
        for i, s in enumerate(info.songs):
            mark = "★" if (i + 1) in info.selected_song_indices else " "
            m, sec = int(s["duration"] // 60), int(s["duration"] % 60)
            print(f"    {mark} {i+1:2d}. {s['title']} ({m}:{sec:02d})")

    if info.images:
        print(f"\n  이미지 ({len(info.images)}장):")
        for i, img in enumerate(info.images):
            mark = "★" if (i + 1) == info.selected_image_index else " "
            print(f"    {mark} {i+1:2d}. {img.get('photographer', '?')} - {img['file']}")

    if info.video_path:
        print(f"\n  영상: {info.video_path}")


# ════════════════════════════════════════════════════════
# PREVIEW — 미리듣기 HTML 생성/열기
# ════════════════════════════════════════════════════════

def cmd_preview(args):
    """미리듣기 HTML 생성하고 브라우저에서 열기."""
    job_dir = get_job_dir(args.job_id)
    info = JobInfo.load(job_dir)
    html_path = build_preview_html(job_dir, info)
    print(f"✅ 미리듣기 페이지: {html_path}")

    if not args.no_open:
        subprocess.Popen(["open", str(html_path)])

    if args.json:
        _print_json({"html_path": str(html_path)})


# ════════════════════════════════════════════════════════
# SELECT-SONGS / SELECT-IMAGE
# ════════════════════════════════════════════════════════

def cmd_select_songs(args):
    """곡 선택 (1-based 인덱스, 콤마 구분)."""
    indices = [int(x.strip()) for x in args.indices.split(",")]
    info = select_songs(args.job_id, indices)
    print(f"✅ 선택된 곡: {info.selected_song_indices}")
    for i in info.selected_song_indices:
        if 1 <= i <= len(info.songs):
            print(f"   {i}. {info.songs[i-1]['title']}")
    if args.json:
        _print_json({"selected": info.selected_song_indices})


def cmd_select_image(args):
    """이미지 선택 (1-based)."""
    info = select_image(args.job_id, args.index)
    if 1 <= args.index <= len(info.images):
        img = info.images[args.index - 1]
        print(f"✅ 선택된 이미지: {img['file']}")
        print(f"   사진작가: {img.get('photographer', '?')}")
    if args.json:
        _print_json({"selected_index": args.index})


# ════════════════════════════════════════════════════════
# FETCH-IMAGES — Unsplash에서 후보 이미지 가져오기
# ════════════════════════════════════════════════════════

def cmd_fetch_images(args):
    """Unsplash에서 후보 이미지 N장 다운로드."""
    from lyrics_gen import fetch_unsplash_image

    cfg = Config.load()
    if not cfg.unsplash_access_key:
        print("❌ Unsplash Access Key 미설정")
        sys.exit(1)

    job_dir = get_job_dir(args.job_id)
    info = JobInfo.load(job_dir)
    images_dir = job_dir / "images"

    print(f"🔍 Unsplash 검색: {info.keyword} ({args.count}장)")
    images = []
    for i in range(args.count):
        img_path = fetch_unsplash_image(info.keyword, cfg.unsplash_access_key, images_dir, anthropic_api_key=cfg.anthropic_api_key)
        if not img_path:
            print(f"   {i+1}. 실패")
            continue
        # 메타데이터 읽기
        meta_file = img_path.with_suffix(img_path.suffix + ".meta.json")
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        images.append({
            "file": img_path.name,
            "photographer": meta.get("photographer_name", "Unknown"),
            "photographer_username": meta.get("photographer_username", ""),
            "photographer_url": meta.get("photographer_url", ""),
            "image_url": meta.get("image_url", ""),
        })
        print(f"   {i+1}. {img_path.name} - {meta.get('photographer_name', '?')}")

    info.images = images
    info.status = STATUS_IMAGES_READY
    info.save(job_dir)

    print(f"\n✅ {len(images)}장 다운로드 완료: {images_dir}")
    if not args.no_open:
        subprocess.Popen(["open", str(images_dir)])
    if args.json:
        _print_json({"images": images})


# ════════════════════════════════════════════════════════
# MAKE-THUMBNAIL — 썸네일 생성
# ════════════════════════════════════════════════════════

def cmd_make_thumbnail(args):
    """선택된 이미지로 썸네일 생성."""
    from media_proc import make_thumbnail

    cfg = Config.load()
    job_dir = get_job_dir(args.job_id)
    info = JobInfo.load(job_dir)

    img_path = get_selected_image_path(args.job_id)
    if not img_path or not img_path.exists():
        print("❌ 선택된 이미지가 없습니다. 'fetch-images' + 'select-image' 먼저 실행")
        sys.exit(1)

    text = args.text or cfg.thumbnail_text or "Seoul Diary Playlist"
    size = args.size or cfg.thumbnail_size or "M"

    thumb_path = job_dir / "thumbnail.jpg"
    make_thumbnail(img_path, text, thumb_path, channel_name=text, size_preset=size)

    info.thumbnail_path = str(thumb_path)
    info.save(job_dir)

    print(f"✅ 썸네일 생성: {thumb_path}")
    if not args.no_open:
        subprocess.Popen(["open", str(thumb_path)])
    if args.json:
        _print_json({"thumbnail": str(thumb_path)})


# ════════════════════════════════════════════════════════
# MAKE-VIDEO — 최종 영상 조립 (재실행 모드)
# ════════════════════════════════════════════════════════

def cmd_make_video(args):
    """선택된 곡 + 썸네일로 최종 영상 생성."""
    from media_proc import make_video, make_thumbnail

    cfg = Config.load()
    job_dir = get_job_dir(args.job_id)
    info = JobInfo.load(job_dir)

    # 곡 가져오기
    selected_mp3s = get_selected_song_paths(args.job_id)
    if not selected_mp3s:
        print("❌ 선택된 곡이 없습니다.")
        sys.exit(1)

    # 썸네일 (없으면 즉석 생성)
    thumb_path = job_dir / "thumbnail.jpg"
    if not thumb_path.exists():
        img_path = get_selected_image_path(args.job_id)
        if not img_path:
            print("❌ 이미지도 썸네일도 없습니다.")
            sys.exit(1)
        text = cfg.thumbnail_text or "Seoul Diary Playlist"
        size = cfg.thumbnail_size or "M"
        make_thumbnail(img_path, text, thumb_path, channel_name=text, size_preset=size)
        print(f"   썸네일 자동 생성: {thumb_path}")

    # 영상 조립
    output_mp4 = job_dir / "output.mp4"
    print(f"🎬 영상 생성 중... ({len(selected_mp3s)}곡)")
    make_video(selected_mp3s, thumb_path, output_mp4)

    info.video_path = str(output_mp4)
    info.status = STATUS_VIDEO_READY
    info.save(job_dir)

    size_mb = output_mp4.stat().st_size / 1024 / 1024
    print(f"✅ 영상 생성 완료: {output_mp4} ({size_mb:.1f} MB)")
    if not args.no_open:
        subprocess.Popen(["open", str(output_mp4.parent)])
    if args.json:
        _print_json({"video": str(output_mp4), "size_mb": round(size_mb, 1)})


# ════════════════════════════════════════════════════════
# DELETE
# ════════════════════════════════════════════════════════

def cmd_delete(args):
    delete_job(args.job_id)
    print(f"✅ 삭제 완료: {args.job_id}")
    if args.json:
        _print_json({"deleted": args.job_id})


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Suno Job Manager CLI")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # create
    p = sub.add_parser("create", help="새 작업 생성")
    p.add_argument("keyword")
    p.add_argument("--lang", default="english", choices=["english", "korean"])
    p.add_argument("--tier", default="T1", choices=["T1", "T2", "T3", "T4"])
    p.add_argument("--customer", default="")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_create)

    # index
    p = sub.add_parser("index", help="songs/ 폴더 스캔하여 job.json에 등록")
    p.add_argument("job_id")
    p.set_defaults(func=cmd_index)

    # gen-lyrics
    p = sub.add_parser("gen-lyrics", help="Claude로 가사/스타일 생성")
    p.add_argument("job_id")
    p.add_argument("--count", type=int, default=3)
    p.set_defaults(func=cmd_gen_lyrics)

    # list
    p = sub.add_parser("list", help="모든 작업 목록")
    p.set_defaults(func=cmd_list)

    # show
    p = sub.add_parser("show", help="작업 상세 정보")
    p.add_argument("job_id")
    p.set_defaults(func=cmd_show)

    # preview
    p = sub.add_parser("preview", help="미리듣기 HTML 생성/열기")
    p.add_argument("job_id")
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(func=cmd_preview)

    # select-songs
    p = sub.add_parser("select-songs", help="곡 선택 (1,3,5)")
    p.add_argument("job_id")
    p.add_argument("indices")
    p.set_defaults(func=cmd_select_songs)

    # fetch-images
    p = sub.add_parser("fetch-images", help="Unsplash 이미지 후보")
    p.add_argument("job_id")
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(func=cmd_fetch_images)

    # select-image
    p = sub.add_parser("select-image", help="이미지 선택")
    p.add_argument("job_id")
    p.add_argument("index", type=int)
    p.set_defaults(func=cmd_select_image)

    # make-thumbnail
    p = sub.add_parser("make-thumbnail", help="썸네일 생성")
    p.add_argument("job_id")
    p.add_argument("--text", default="")
    p.add_argument("--size", default="", choices=["", "M", "XL"])
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(func=cmd_make_thumbnail)

    # make-video
    p = sub.add_parser("make-video", help="최종 영상 조립")
    p.add_argument("job_id")
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(func=cmd_make_video)

    # delete
    p = sub.add_parser("delete", help="작업 삭제")
    p.add_argument("job_id")
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
