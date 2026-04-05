"""
lyrics_gen.py — Claude API로 가사/스타일/YouTube 정보 생성

모델: claude-haiku-4-5-20251001
응답은 JSON만 반환하도록 프롬프트 작성.
"""

from __future__ import annotations

import re
import json
from pathlib import Path

import anthropic

MODEL = "claude-haiku-4-5-20251001"


# ------------------------------------------------------------------ #
# 내부 헬퍼                                                            #
# ------------------------------------------------------------------ #

def _call_claude(api_key: str, prompt: str) -> str:
    """Claude API를 호출하고 텍스트 응답을 반환한다."""
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _parse_json(text: str) -> dict:
    """응답에서 JSON 블록을 추출해 파싱한다."""
    # 코드 블록 안 JSON 시도
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # 중괄호 직접 추출
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"JSON을 파싱할 수 없습니다. 원본 응답:\n{text}")


# ------------------------------------------------------------------ #
# 공개 함수                                                            #
# ------------------------------------------------------------------ #

def generate_song_content(
    keyword: str,
    language: str,
    index: int,
    api_key: str,
) -> dict:
    """
    키워드와 언어를 기반으로 가사와 스타일을 생성한다.

    Args:
        keyword:  노래 주제 키워드 (예: "lofi chill", "가을 감성")
        language: "korean" 또는 "english"
        index:    0부터 시작하는 곡 인덱스 (다양한 버전 생성용)
        api_key:  Anthropic API 키

    Returns:
        {"lyrics": str, "style": str}
    """
    lang_instruction = (
        "한국어로 작성하세요. 가사는 반드시 한국어여야 합니다."
        if language == "korean"
        else "Write in English. The lyrics must be in English."
    )

    variety_note = (
        f"이것은 {index + 1}번째 버전입니다. 이전 버전과 다른 분위기로 작성하세요."
        if index > 0
        else ""
    )

    prompt = f"""당신은 전문 작사가입니다. 아래 키워드를 바탕으로 노래 제목, 가사, 음악 스타일을 만들어주세요.

키워드: {keyword}
{lang_instruction}
{variety_note}

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "창의적인 노래 제목 (감성적이고 독특하게, 키워드를 그대로 쓰지 말고 변형)",
  "lyrics": "완성된 가사 (최소 4절, 각 절 4줄 이상, [Verse 1], [Chorus] 등 섹션 레이블)",
  "style": "음악 스타일 (영어, 콤마 구분, 50자 이내, 예: lo-fi hip hop, chill, warm, nostalgic)"
}}

주의사항:
- title은 감성적이고 기억에 남는 제목이어야 합니다. "{keyword} Ver.1" 같은 건 절대 안 됩니다.
- lyrics는 완성된 노래 가사여야 합니다.
- style은 Suno.com의 Style of Music 입력창에 넣을 짧은 영어 설명입니다.
- JSON 외 다른 텍스트는 절대 포함하지 마세요."""

    try:
        response = _call_claude(api_key, prompt)
        result = _parse_json(response)

        if "lyrics" not in result or "style" not in result:
            raise ValueError("응답에 'lyrics' 또는 'style' 키가 없습니다.")

        return {
            "title": str(result.get("title", keyword)).strip(),
            "lyrics": str(result["lyrics"]).strip(),
            "style": str(result["style"]).strip(),
        }
    except Exception as e:
        raise RuntimeError(f"가사/스타일 생성 실패 (keyword={keyword}, lang={language}): {e}") from e


def generate_youtube_info(
    keyword: str,
    total_songs: int,
    api_key: str,
) -> dict:
    """
    키워드를 기반으로 YouTube 업로드 정보를 생성한다.

    Args:
        keyword:     노래 주제 키워드
        total_songs: 플레이리스트에 포함될 총 곡 수
        api_key:     Anthropic API 키

    Returns:
        {"title": str, "description": str, "tags": list[str]}
    """
    prompt = f"""당신은 YouTube 음악 채널 운영자입니다. 아래 정보를 바탕으로 YouTube 동영상 정보를 만들어주세요.

키워드: {keyword}
총 곡 수: {total_songs}곡

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "YouTube 영상 제목 (50자 이내, 한국어/영어 혼용 가능, 감성적으로)",
  "description": "YouTube 영상 설명 (200자 이내, 키워드 관련 분위기 묘사, 해시태그 포함)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5", "태그6", "태그7", "태그8"]
}}

주의사항:
- title은 클릭을 유도하는 매력적인 제목이어야 합니다.
- description에는 #suno #aimusic 등 관련 해시태그를 포함하세요.
- tags는 최소 8개, 영어와 한국어 혼용 가능.
- JSON 외 다른 텍스트는 절대 포함하지 마세요."""

    try:
        response = _call_claude(api_key, prompt)
        result = _parse_json(response)

        if "title" not in result or "description" not in result or "tags" not in result:
            raise ValueError("응답에 필수 키(title/description/tags)가 없습니다.")

        tags = result["tags"]
        if not isinstance(tags, list):
            tags = [str(tags)]

        return {
            "title": str(result["title"]).strip(),
            "description": str(result["description"]).strip(),
            "tags": [str(t).strip() for t in tags],
        }
    except Exception as e:
        raise RuntimeError(f"YouTube 정보 생성 실패 (keyword={keyword}): {e}") from e


def generate_instrumental_description(keyword: str, api_key: str) -> str:
    """
    키워드를 기반으로 Suno Instrumental 모드용 Song Description을 생성한다.
    프로젝트당 1회 호출, 모든 instrumental 세션에서 공유.

    Returns:
        영어 설명 문자열 (200자 이내)
    """
    prompt = f"""You are a music producer creating an instrumental track.

Theme/keyword: {keyword}

Write a "Song Description" for Suno.com's instrumental mode (under 200 characters).
Describe the mood, instruments, tempo, and genre. Be specific and vivid.
Write in English only. Do NOT include lyrics or song titles.

Reply with ONLY the description text, nothing else."""

    try:
        return _call_claude(api_key, prompt).strip()[:200]
    except Exception:
        return keyword


def fetch_pixabay_image(keyword: str, api_key: str, save_dir: Path) -> Path | None:
    """
    Pixabay에서 키워드 기반 이미지를 다운로드한다.

    Returns:
        저장된 이미지 Path, 또는 실패 시 None
    """
    import urllib.request
    import urllib.parse

    if not api_key:
        return None

    save_dir.mkdir(parents=True, exist_ok=True)
    query = urllib.parse.quote(keyword)
    url = (
        f"https://pixabay.com/api/?key={api_key}&q={query}"
        f"&image_type=photo&orientation=horizontal&per_page=5&safesearch=true"
    )

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        hits = data.get("hits", [])
        if not hits:
            return None

        # 첫 번째 결과의 큰 이미지 다운로드
        img_url = hits[0].get("largeImageURL") or hits[0].get("webformatURL")
        if not img_url:
            return None

        ext = Path(urllib.parse.urlparse(img_url).path).suffix or ".jpg"
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in keyword)[:30]
        save_path = save_dir / f"{safe_name}{ext}"

        urllib.request.urlretrieve(img_url, save_path)
        return save_path

    except Exception:
        return None
