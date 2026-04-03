"""
가사 및 콘텐츠 생성 모듈
Claude Haiku 4.5 + vision으로 키워드+이미지 → 가사/스타일/유튜브 제목+설명 생성.

실행: python suno_lyrics_gen.py --keyword "sunset calm" --image cover.jpg
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import anthropic


def generate_content(
    keyword: str,
    image_path: str = None,
    api_key: str = "",
    base_style: str = "cinematic, orchestral, emotional",
    vocal: str = "female",
    channel_style: dict = None,
    performance_hint: str = "",
) -> dict:
    """
    키워드(+이미지)를 바탕으로 Suno용 가사/스타일/유튜브 제목+설명을 생성.
    channel_style이 있으면 해당 채널 스타일로 YouTube 제목/설명 생성.

    Returns:
        {
            "lyrics":            "가사",
            "style":             "Suno 스타일 프롬프트 (영어)",
            "song_title":        "곡 제목",
            "youtube_title":     "YouTube 영상 제목",
            "youtube_description": "YouTube 설명 (여러 줄 + 해시태그)",
            "tags":              ["tag1", ...]
        }
    """
    client = anthropic.Anthropic(api_key=api_key)

    # 이미지 인코딩
    image_block = None
    if image_path and Path(image_path).exists():
        raw = Path(image_path).read_bytes()
        b64 = base64.standard_b64encode(raw).decode()
        suffix = Path(image_path).suffix.lower()
        media_type = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",  ".webp": "image/webp",
        }.get(suffix, "image/jpeg")
        image_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }

    style_with_vocal = f"{base_style}, {vocal} vocal"

    # YouTube 스타일 힌트 (채널 분석 결과 있으면 포함)
    yt_style_hint = ""
    if channel_style:
        title_tmpl = channel_style.get("title_template", "")
        desc_tmpl  = channel_style.get("description_template", "")
        notes      = channel_style.get("style_notes", "")
        if title_tmpl or notes:
            yt_style_hint = f"""
YouTube 제목/설명은 아래 채널 스타일을 참고해서 작성하세요:
- 제목 패턴: {title_tmpl}
- 설명 패턴: {desc_tmpl}
- 채널 특징: {notes}
"""

    # 성과 피드백 힌트
    perf_section = ""
    if performance_hint:
        perf_section = f"\n{performance_hint}\n"

    prompt_text = f"""키워드: "{keyword}"
기본 스타일: {style_with_vocal}
{yt_style_hint}{perf_section}
{"위 이미지와 " if image_block else ""}키워드를 바탕으로 Suno AI 음악 생성을 위한 콘텐츠를 만들어 주세요.

JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "lyrics":             "감성적인 가사 (4~8줄, 한국어 또는 영어)",
  "style":              "Suno 스타일 프롬프트 (영어, 쉼표 구분, 예: cinematic, orchestral, female vocal)",
  "song_title":         "곡 제목 (한국어 또는 영어, 짧고 감성적으로)",
  "youtube_title":      "YouTube 영상 제목 (채널 스타일 반영, 이모지 포함, 60자 이내)",
  "youtube_description": "YouTube 설명 (한국어, 4~6줄, 감성적인 소개 + 해시태그 5개 이상)",
  "tags":               ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}"""

    content_blocks = []
    if image_block:
        content_blocks.append(image_block)
    content_blocks.append({"type": "text", "text": prompt_text})

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": content_blocks}],
    )

    raw = resp.content[0].text.strip()

    # ```json ... ``` 블록 처리
    if "```" in raw:
        for part in raw.split("```")[1::2]:
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue

    return json.loads(raw)


def _fallback_content(keyword: str, base_style: str, vocal: str) -> dict:
    """API 실패 시 키워드 기반 기본값 생성."""
    return {
        "lyrics":      f"[{keyword}]\n\n바람이 불어오는 곳\n그 곳으로 가고 싶어\n{keyword}의 빛 속에서\n새로운 하루가 시작돼",
        "style":       f"{base_style}, {vocal} vocal",
        "song_title":  keyword,
        "youtube_title":       f"🎵 {keyword} — AI Music",
        "youtube_description": f"✨ {keyword}\n\nAI로 생성한 음악입니다.\n\n#AIMusic #Suno #{keyword.replace(' ','')}",
        "tags":        ["AI music", "Suno", keyword, "감성", "K-pop"],
    }


def generate_content_safe(
    keyword: str,
    image_path: str = None,
    api_key: str = "",
    base_style: str = "cinematic, orchestral, emotional",
    vocal: str = "female",
    channel_style: dict = None,
    performance_hint: str = "",
) -> dict:
    """generate_content의 안전한 래퍼 (실패 시 fallback 반환)."""
    try:
        return generate_content(keyword, image_path, api_key,
                                base_style, vocal, channel_style,
                                performance_hint)
    except Exception as e:
        print(f"[lyrics_gen] 생성 실패 ({e}), 기본값 사용")
        return _fallback_content(keyword, base_style, vocal)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Claude Haiku로 가사/스타일/유튜브 제목+설명 생성")
    parser.add_argument("--keyword",  required=True, help="곡 키워드")
    parser.add_argument("--image",    default=None,  help="커버 이미지 경로")
    parser.add_argument("--style",    default="cinematic, orchestral, emotional")
    parser.add_argument("--vocal",    default="female",
                        choices=["female", "male", "none"])
    parser.add_argument("--api-key",  default="")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # config 파일에서도 시도
        cfg_file = Path.home() / ".suno_config.json"
        if cfg_file.exists():
            try:
                api_key = json.loads(cfg_file.read_text())["anthropic_api_key"]
            except Exception:
                pass
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 가 없습니다.")
        sys.exit(1)

    print(f"키워드: {args.keyword}")
    print(f"이미지: {args.image or '없음'}")
    print("생성 중...\n")

    result = generate_content_safe(args.keyword, args.image, api_key, args.style, args.vocal)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
