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

def _call_claude(api_key: str, prompt: str, temperature: float = 1.0) -> str:
    """Claude API를 호출하고 텍스트 응답을 반환한다."""
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        temperature=temperature,
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

    import random

    # 매번 다른 조합을 랜덤으로 배정해서 같은 결과가 나올 수 없게 함
    tone_pool = [
        "hopeful and bright", "melancholic and dreamy", "upbeat and groovy",
        "calm and meditative", "passionate and intense", "playful and quirky",
        "dark and moody", "warm and cozy", "ethereal and floating",
        "funky and bold", "tender and delicate", "rebellious and raw",
        "cinematic and grand", "minimal and stripped", "jazzy and smooth",
        "nostalgic and bittersweet", "cheerful and sunny", "mysterious and hypnotic",
    ]
    genre_pool = [
        "indie pop", "jazz pop", "lo-fi hip hop", "R&B soul", "acoustic folk",
        "synth pop", "bossa nova", "dream pop", "soft rock", "neo soul",
        "city pop", "electro swing", "ambient", "bedroom pop", "funk",
        "shoegaze", "trip hop", "progressive pop", "chamber pop", "afrobeat",
    ]
    title_style_pool = [
        "한 단어 제목 (예: Bloom, Driftwood, Mirage)",
        "장소 + 감정 (예: Rooftop Melancholy, Subway Daydream)",
        "시간 + 행동 (예: 3AM Confessions, Sunday Morning Rewind)",
        "색깔 + 명사 (예: Crimson Letters, Silver Lining Rain)",
        "의인화 (예: The Moon Wrote Back, Clouds Don't Apologize)",
        "질문형 (예: Did You Hear the Rain?, Where Do Lost Songs Go?)",
        "대화체 (예: Hey, It's Me Again / Don't Look Back Now)",
        "감각 묘사 (예: Cinnamon Air, Velvet Horizons)",
    ]
    chosen_tone = random.choice(tone_pool)
    chosen_genre = random.choice(genre_pool)
    chosen_title_style = random.choice(title_style_pool)
    random_seed = random.randint(1000, 9999)

    variety_note = (
        f"\n⚠️ 이것은 {index + 1}번째 곡입니다. 이전 곡과 완전히 다른 제목, 다른 분위기, 다른 가사를 쓰세요."
        if index > 0 else ""
    )

    prompt = f"""당신은 Seoul Diary Playlist 채널의 전속 작사가입니다.
감성적이고 퀄리티 높은 노래를 작곡해주세요.

═══════════════════════════════════════
키워드: {keyword}
{lang_instruction}
이 곡의 감정 톤: {chosen_tone}
이 곡의 장르: {chosen_genre}
제목 스타일: {chosen_title_style}
랜덤 시드: {random_seed}
{variety_note}
═══════════════════════════════════════

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "노래 제목",
  "lyrics": "가사",
  "style": "Suno 스타일 태그"
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[제목 규칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 이 곡의 제목 스타일: {chosen_title_style}
- 위 스타일을 참고하되 독창적으로 만드세요
- 키워드를 그대로 제목에 넣지 마세요
- 3~6단어, 짧고 임팩트 있게
- 매번 완전히 다른 제목이어야 합니다

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[가사 규칙 — 매우 중요!]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 구조: [Verse 1] → [Chorus] → [Verse 2] → [Chorus] → [Bridge] → [Chorus] → [Outro]
- 각 섹션 3~4줄 (너무 길면 노래가 5분을 넘김)
- 총 가사 길이: 800~1200자 이내 (5분 이하 곡이 되도록)
- [Chorus]는 반복 가능하지만 가사가 동일해야 합니다
- 감정선: Verse에서 이야기 → Chorus에서 폭발 → Bridge에서 전환 → Outro에서 여운
- 키워드의 감성을 녹여서, 구체적인 장면이 떠오르는 가사
- 진부한 표현 피하기 (love, heart, soul 남발 금지)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[스타일 규칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Suno.com의 "Style of Music" 입력용 (영어, 콤마 구분)
- 반드시 "{chosen_genre}" 계열 포함
- "{chosen_tone}" 분위기 반영
- 구체적 악기/사운드 1~2개 포함 (예: soft piano, muted trumpet, fingerpicked guitar)
- 50자 이내

JSON 외 다른 텍스트는 절대 포함하지 마세요."""

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
    prompt = f"""당신은 "Seoul Diary Playlist" 감성 재즈팝 플레이리스트 채널의 운영자입니다.
아래 키워드를 바탕으로 YouTube 영상 정보를 만들어주세요.

키워드: {keyword}
총 곡 수: {total_songs}곡

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "영상 제목 (한국어 감성 + 영어 부제) | Seoul Diary Playlist",
  "description": "영상 설명 (영어, 감성적 산문체)",
  "tags": ["태그1", "태그2", ...]
}}

[title 작성 규칙]
실제 채널의 제목 스타일:
- "산타렐리를 기다리며 | Christmas Jazz Playlist | Seoul Diary Playlist"
- "크리스마스가 스며드는 재즈 팝 | Seoul Diary Playlist"
- "Wavy Nights in Gwangalli | Seoul Diary Playlist"
- "Fancy Evening in Seongsu | Seoul Diary Playlist"
- "I Wish You Happiness | Seoul Diary Playlist"
- "Naksan Park Night Walk Jazz Pop | Seoul Diary Playlist"

규칙:
1. 제목 끝에 반드시 "| Seoul Diary Playlist" 포함
2. 한국어 감성 문구 또는 영어 장소+분위기 조합
3. 키워드를 자연스럽게 녹여서 장소/분위기로 변환
4. 50자 이내 (Seoul Diary Playlist 부분 제외)

[description 작성 규칙]
실제 채널의 설명 스타일 (영어로 작성):
- 2-3줄의 감성적 산문체 도입부 (도시, 계절, 분위기 묘사)
- 이모지 자연스럽게 사용 (🌙✨🎶 등)
- 마지막에 아래 고정 문구 포함:

📌 All tracks are original compositions created with AI music tools.
🎵 Music generated using Suno AI — composed, curated, and arranged by Seoul Diary Playlist.
⚠️ All content on this channel is original. No copyrighted material is used.

❤️ If you enjoyed the vibe, please like, subscribe, and share!
🔔 Turn on notifications so you never miss a new playlist.

#playlist #SeoulDiaryPlaylist #jazzpop #감성플리 #aimusic

5. 도입부는 3-4문장, 영어로 감성적으로 작성
6. 저작권 고지 문구는 반드시 포함 (AI 생성 음악임을 명시)

[tags 규칙]
- 최소 10개
- 영어/한국어 혼용
- 필수 포함: playlist, SeoulDiaryPlaylist, jazzpop, 감성플리, aimusic, suno
- 키워드 관련 태그 추가

JSON 외 다른 텍스트는 절대 포함하지 마세요."""

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


def _keyword_to_english(keyword: str) -> str:
    """한글 키워드를 Pixabay 검색용 영어로 변환 (간단한 매핑 + 원본 시도)"""
    # 한글이 포함되어 있으면 감성적 영어 키워드로 변환
    has_korean = any('\uAC00' <= c <= '\uD7A3' for c in keyword)
    if not has_korean:
        return keyword

    # 주요 감성 키워드 매핑
    mappings = {
        "봄": "spring flowers", "여름": "summer ocean", "가을": "autumn leaves",
        "겨울": "winter snow", "바람": "wind nature", "비": "rain city",
        "밤": "night city lights", "새벽": "dawn sky", "노을": "sunset",
        "바다": "ocean waves", "하늘": "sky clouds", "별": "starry night",
        "꽃": "flower field", "도시": "city night", "거리": "street night",
        "카페": "cafe aesthetic", "창문": "window rain", "숲": "forest light",
        "사랑": "love aesthetic", "그리움": "nostalgia vintage", "감성": "aesthetic mood",
        "드라이브": "night drive", "여행": "travel scenery", "추억": "memories vintage",
    }
    parts = []
    for k, v in mappings.items():
        if k in keyword:
            parts.append(v)
    return " ".join(parts) if parts else "aesthetic mood landscape"


def fetch_pixabay_image(keyword: str, api_key: str, save_dir: Path) -> Path | None:
    """
    Pixabay에서 키워드 기반 이미지를 다운로드한다.
    한글 키워드는 영어로 변환하여 검색.

    Returns:
        저장된 이미지 Path, 또는 실패 시 None
    """
    import urllib.request
    import urllib.parse

    if not api_key:
        return None

    save_dir.mkdir(parents=True, exist_ok=True)

    # 한글 → 영어 변환
    search_term = _keyword_to_english(keyword)
    query = urllib.parse.quote(search_term)
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

        req = urllib.request.Request(img_url, headers={"User-Agent": "SunoAutoPlaylist/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            save_path.write_bytes(resp.read())
        return save_path

    except Exception:
        return None
