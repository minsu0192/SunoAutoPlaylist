"""
가사 및 콘텐츠 생성 모듈
Claude Haiku 4.5 + vision으로 키워드+이미지 → 가사/스타일/유튜브 설명 생성.

실행: python suno_lyrics_gen.py --keyword "sunset calm" --image cover.jpg
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import anthropic


def generate_content(
    keyword: str,
    image_path: str = None,
    api_key: str = "",
    base_style: str = "cinematic, orchestral, emotional",
    vocal: str = "female",
) -> dict:
    """
    키워드(+이미지)를 바탕으로 Suno용 가사/스타일/유튜브 설명을 생성.

    Returns:
        {
            "lyrics":      "가사 텍스트 (4~8줄)",
            "style":       "Suno 스타일 프롬프트 (영어)",
            "description": "유튜브 설명 (한국어, 3~5줄)",
            "tags":        ["tag1", "tag2", ...]
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
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")
        image_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }

    style_with_vocal = f"{base_style}, {vocal} vocal"

    prompt_text = f"""키워드: "{keyword}"
기본 스타일: {style_with_vocal}

{"위 이미지와 " if image_block else ""}키워드를 바탕으로 Suno AI 음악 생성을 위한 콘텐츠를 만들어 주세요.

JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "lyrics": "감성적인 가사 (4~8줄, 한국어 또는 영어, 키워드 분위기에 맞게)",
  "style": "Suno 스타일 프롬프트 (영어, 쉼표 구분, 예: cinematic, orchestral, female vocal, emotional, 120bpm)",
  "description": "유튜브 영상 설명 (한국어, 3~5줄, 감성적으로, 해시태그 포함)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}"""

    content_blocks = []
    if image_block:
        content_blocks.append(image_block)
    content_blocks.append({"type": "text", "text": prompt_text})

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": content_blocks}],
    )

    raw = resp.content[0].text.strip()

    # ```json ... ``` 블록 처리
    if "```" in raw:
        parts = raw.split("```")
        for part in parts[1::2]:  # 홀수 인덱스 = 코드블록 내용
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue

    return json.loads(raw)


def _fallback_content(keyword: str, base_style: str, vocal: str) -> dict:
    """API 실패 시 키워드 기반 기본값 생성."""
    return {
        "lyrics": f"[{keyword}]\n\n바람이 불어오는 곳\n그 곳으로 가고 싶어\n{keyword}의 빛 속에서\n새로운 하루가 시작돼",
        "style": f"{base_style}, {vocal} vocal",
        "description": f"✨ {keyword}\n\nAI로 생성한 음악입니다.\n\n#AIMusic #Suno #{keyword.replace(' ', '')}",
        "tags": ["AI music", "Suno", "K-pop", keyword, "감성"],
    }


def generate_content_safe(
    keyword: str,
    image_path: str = None,
    api_key: str = "",
    base_style: str = "cinematic, orchestral, emotional",
    vocal: str = "female",
) -> dict:
    """generate_content의 안전한 래퍼 (실패 시 fallback 반환)."""
    try:
        return generate_content(keyword, image_path, api_key, base_style, vocal)
    except Exception as e:
        print(f"[lyrics_gen] 생성 실패 ({e}), 기본값 사용")
        return _fallback_content(keyword, base_style, vocal)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Claude Haiku로 가사/스타일/설명 생성")
    parser.add_argument("--keyword", required=True, help="곡 키워드")
    parser.add_argument("--image",   default=None,  help="커버 이미지 경로")
    parser.add_argument("--style",   default="cinematic, orchestral, emotional", help="기본 스타일")
    parser.add_argument("--vocal",   default="female", choices=["female", "male", "none"], help="보컬 타입")
    parser.add_argument("--api-key", default="", help="Anthropic API 키 (없으면 환경변수 사용)")
    args = parser.parse_args()

    import os
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
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
