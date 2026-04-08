"""
lyrics_gen.py — Claude API로 가사/스타일/YouTube 정보 생성

모델: claude-haiku-4-5-20251001
응답은 JSON만 반환하도록 프롬프트 작성.
"""

from __future__ import annotations

import random
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
    used_titles: list[str] | None = None,
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

    titles_note = ""
    if used_titles:
        titles_list = ", ".join(f'"{t}"' for t in used_titles)
        titles_note = f"\n⚠️ ALREADY USED TITLES (do NOT reuse or closely resemble these): {titles_list}"

    prompt = f"""You are the exclusive songwriter for "Seoul Diary Playlist," a YouTube channel that creates cinematic, emotionally rich music inspired by the streets, seasons, and stories of Seoul. Your songs have been streamed by hundreds of thousands of listeners who come for the atmosphere — the feeling of walking through rain-soaked alleys, watching city lights from a rooftop café, or sitting alone on a park bench as autumn leaves fall.

Your job: write ONE complete song based on the keyword below. Every song you write should feel like a scene from a film — vivid, specific, and emotionally honest.

═══════════════════════════════════════════════════
KEYWORD: {keyword}
LANGUAGE: {language}
EMOTIONAL TONE: {chosen_tone}
GENRE: {chosen_genre}
TITLE STYLE: {chosen_title_style}
RANDOM SEED: {random_seed}
{variety_note}{titles_note}
═══════════════════════════════════════════════════

Respond with ONLY this JSON (no other text):
{{
  "title": "song title",
  "lyrics": "full lyrics",
  "style": "Suno style tags"
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TITLE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Follow this title style: {chosen_title_style}
- 3~6 words, memorable and evocative
- Do NOT use the keyword "{keyword}" literally — transform it poetically
- Avoid generic titles like "Beautiful Day" or "Love Song"
- Think of titles that make someone curious enough to click:
  Good: "Neon Puddles After Midnight", "The Café Closes at Dawn"
  Bad: "Sad Autumn Song", "Whispers of Love"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LYRICS RULES (CRITICAL — READ CAREFULLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{lang_instruction}

STRUCTURE (follow this exactly):
[Verse 1] — 4 lines. Set the scene. Where are we? What do we see/hear/smell?
[Chorus] — 3~4 lines. The emotional core. Catchy, singable, repeatable.
[Verse 2] — 4 lines. Deepen the story. What changed? What do we feel now?
[Chorus] — Same lyrics as first chorus.
[Bridge] — 2~3 lines. A shift — new perspective, confession, or turning point.
[Chorus] — Same lyrics again.
[Outro] — 1~2 lines. A lingering final image. Leave the listener wanting more.

QUALITY GUIDELINES:
- Total lyrics: 600~1000 characters (this produces a 3~4 minute song on Suno)
- Each line should paint a SPECIFIC image, not abstract feelings
  Good: "Steam rises from the cup you left behind"
  Bad: "I feel so sad without you here"
- Use sensory language: colors, textures, temperatures, sounds
- The chorus should have a melodic rhythm — read it aloud, it should flow
- Avoid overused words: whisper, echo, fade, glow, heart, soul (unless truly fitting)
- Tell a mini-story: beginning (Verse 1) → middle (Verse 2) → twist (Bridge) → end (Outro)
- Reference real places, objects, moments — make it feel LIVED, not written

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STYLE RULES (for Suno.com "Style of Music" input)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- English, comma-separated tags, MAX 50 characters
- MUST include a variation of "{chosen_genre}"
- MUST reflect the "{chosen_tone}" mood
- Include 1~2 specific instruments or production elements:
  Examples: "muted trumpet", "Rhodes piano", "tape-saturated drums",
  "fingerpicked nylon guitar", "vinyl crackle", "soft brush drums",
  "warm analog synth", "upright bass pizzicato"
- Think about what a LISTENER would search for, not what a musician would write
  Good: "jazz pop, warm, muted trumpet, late night café vibes"
  Bad: "Cmaj7 progression with ii-V-I turnaround"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REMEMBER: Output ONLY the JSON. No explanations, no markdown, no extra text."""

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


# 한글 키워드 → 영어 동의어 풀 (각 키워드마다 여러 동의어, 매번 랜덤 선택)
KEYWORD_SYNONYMS: dict[str, list[str]] = {
    "봄": ["spring blossoms", "cherry blossom", "spring flowers", "spring meadow", "vernal bloom", "april flowers"],
    "여름": ["summer ocean", "tropical beach", "summer sunset", "ocean waves", "azure sea", "sunlit shore"],
    "가을": ["autumn leaves", "fallen leaves", "autumn forest", "maple foliage", "amber leaves", "golden autumn"],
    "겨울": ["winter snow", "snowfall city", "frozen lake", "snowy forest", "frost morning", "winter mist"],
    "바람": ["windy field", "windswept grass", "breeze nature", "windy meadow", "swaying trees"],
    "비": ["rain city", "raindrops window", "rainy street", "wet pavement neon", "rainstorm reflection", "drizzle alley"],
    "밤": ["night city lights", "midnight street", "nocturne skyline", "neon nightscape", "after dark city", "evening cityscape"],
    "새벽": ["dawn sky", "predawn fog", "twilight horizon", "first light", "blue hour", "early morning mist", "daybreak silhouette"],
    "노을": ["sunset glow", "golden hour sky", "dusk horizon", "sunset clouds", "evening sky", "magic hour"],
    "바다": ["ocean waves", "sea horizon", "tranquil sea", "coastal mist", "moody ocean", "deep blue sea"],
    "하늘": ["dramatic sky", "cloudscape", "sunset clouds", "stormy sky", "ethereal sky", "cinematic clouds"],
    "별": ["starry night", "milky way", "night sky stars", "constellation", "astrophotography"],
    "꽃": ["flower field", "wildflowers", "floral aesthetic", "delicate petals", "bloom macro"],
    "도시": ["city skyline", "urban night", "metropolis lights", "downtown neon", "cityscape rain", "tokyo street"],
    "거리": ["empty street night", "alley neon", "rainy street", "cobblestone alley", "moody alley", "street lamp glow"],
    "카페": ["cozy cafe", "coffee shop window", "espresso bar", "vintage cafe", "warm cafe interior", "rainy cafe"],
    "창문": ["rainy window", "window light", "foggy window", "cafe window", "raindrops glass"],
    "숲": ["misty forest", "foggy woods", "forest light rays", "ancient forest", "cinematic forest"],
    "사랑": ["aesthetic couple", "soft romance", "tender moment", "warm embrace"],
    "그리움": ["vintage nostalgia", "old photograph", "nostalgic mood", "faded memories", "retro aesthetic"],
    "감성": ["aesthetic mood", "moody atmosphere", "cinematic vibes", "ethereal feeling"],
    "드라이브": ["night drive", "neon road", "highway lights", "car window night", "road trip dusk"],
    "여행": ["travel landscape", "wanderlust scenery", "scenic vista", "journey horizon"],
    "추억": ["vintage memories", "old film grain", "retro polaroid", "nostalgic scene"],
    "lofi": ["lofi aesthetic", "study desk warm", "cozy room window", "vinyl record warm", "lofi room"],
    "재즈": ["jazz bar dim", "vintage jazz club", "saxophone neon", "smoky jazz lounge"],
}

# 감성 모디파이어 풀 (매번 1~2개 랜덤 선택해서 검색어에 추가)
AESTHETIC_MODIFIERS = [
    "aesthetic", "moody", "cinematic", "dreamy", "atmospheric",
    "nostalgic", "ethereal", "melancholic", "noir", "vintage",
    "film grain", "bokeh", "golden hour", "blue hour", "neon lights",
    "soft light", "warm tones", "foggy", "misty", "ambient light",
    "muted colors", "low light", "dramatic", "minimal aesthetic",
]

# 폴백 키워드 풀 (한글 매핑 못 찾았을 때)
FALLBACK_SUBJECTS = [
    "aesthetic landscape", "moody scene", "cinematic vista",
    "atmospheric mood", "dreamy nature", "ethereal place",
]


def _keyword_to_english(keyword: str, simple: bool = False) -> str:
    """
    한글 키워드를 Pixabay 검색용 영어로 변환.
    매번 다른 동의어를 랜덤 선택하여 검색 결과 다양성을 극대화한다.

    Args:
        simple: True면 모디파이어 없이 주제어 1개만 (검색 결과 0개일 때 폴백용)
    """
    has_korean = any('\uAC00' <= c <= '\uD7A3' for c in keyword)

    # 매칭되는 키워드의 동의어 중 랜덤 선택 (주제어 1개만)
    subjects: list[str] = []
    for k, synonyms in KEYWORD_SYNONYMS.items():
        if k in keyword:
            subjects.append(random.choice(synonyms))

    if subjects:
        # 매칭된 주제 중 1개만 선택 (너무 specific한 쿼리 방지)
        subject = random.choice(subjects)
    elif not has_korean:
        # 영어 키워드는 그대로 (가장 첫 1~2 단어만)
        words = keyword.split()[:2]
        subject = " ".join(words)
    else:
        # 매칭 안 되는 한글 → 폴백
        subject = random.choice(FALLBACK_SUBJECTS)

    if simple:
        return subject

    # 감성 모디파이어 1개만 추가 (너무 많이 붙이면 검색 결과 0개)
    modifier = random.choice(AESTHETIC_MODIFIERS)
    return f"{subject} {modifier}"


# 사용한 이미지 ID 이력 파일
IMAGE_HISTORY_FILE = Path.home() / ".suno_image_history.json"


def _load_image_history() -> set[int]:
    """사용한 Pixabay 이미지 ID 집합을 로드."""
    if not IMAGE_HISTORY_FILE.exists():
        return set()
    try:
        data = json.loads(IMAGE_HISTORY_FILE.read_text(encoding="utf-8"))
        return set(int(x) for x in data)
    except Exception:
        return set()


def _save_image_history(history: set[int]) -> None:
    """사용한 이미지 ID 집합을 저장 (최근 1000개만 유지)."""
    try:
        # 너무 많이 쌓이지 않게 최근 1000개만 유지
        kept = sorted(history)[-1000:]
        IMAGE_HISTORY_FILE.write_text(json.dumps(kept), encoding="utf-8")
    except Exception:
        pass


def fetch_pixabay_image(keyword: str, api_key: str, save_dir: Path) -> Path | None:
    """
    Pixabay에서 감성적이고 중복 없는 이미지를 다운로드한다.

    전략:
    1. 한글 키워드 → 동의어 풀에서 랜덤 선택 (매번 다른 검색어)
    2. 감성 모디파이어 1~2개 랜덤 추가
    3. per_page=50, order=popular로 50개 후보 확보
    4. 랜덤 페이지(1~5)에서 가져옴
    5. 이미지 ID 이력에서 사용한 것은 제외
    6. 남은 후보 중 랜덤 선택, 새 ID는 이력에 추가
    """
    import urllib.request
    import urllib.parse

    if not api_key:
        return None

    save_dir.mkdir(parents=True, exist_ok=True)

    history = _load_image_history()

    def _search(search_term: str, page: int) -> list[dict]:
        query = urllib.parse.quote(search_term)
        url = (
            f"https://pixabay.com/api/?key={api_key}&q={query}"
            f"&image_type=photo&orientation=horizontal"
            f"&per_page=50&page={page}&safesearch=true&order=popular"
        )
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            return data.get("hits", [])
        except Exception:
            return []

    # 최대 5번 시도 (다른 검색어/페이지로 재시도)
    chosen = None
    for attempt in range(5):
        # 첫 3번: 풀 쿼리(주제+모디파이어). 마지막 2번: 단순 쿼리(주제만)
        simple = attempt >= 3
        search_term = _keyword_to_english(keyword, simple=simple)
        page = random.randint(1, 5)
        hits = _search(search_term, page)

        if not hits:
            # 결과 0개 → 페이지 1로 재시도
            hits = _search(search_term, 1)
            if not hits:
                continue

        # 이력에 없는 이미지만 필터링
        fresh = [h for h in hits if h.get("id") not in history]

        if fresh:
            chosen = random.choice(fresh)
            break
        # 다 사용한 경우 → 다른 검색어로 재시도

    # 5번 시도해도 fresh 없으면 가장 일반적인 검색으로 재사용
    if chosen is None:
        hits = _search("aesthetic mood landscape", 1)
        if not hits:
            return None
        chosen = random.choice(hits)

    img_url = chosen.get("largeImageURL") or chosen.get("webformatURL")
    if not img_url:
        return None

    img_id = chosen.get("id")
    ext = Path(urllib.parse.urlparse(img_url).path).suffix or ".jpg"
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in keyword)[:30]
    save_path = save_dir / f"{safe_name}_{img_id}{ext}"

    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": "SunoAutoPlaylist/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            save_path.write_bytes(resp.read())
    except Exception:
        return None

    # 이력에 추가
    if img_id is not None:
        history.add(int(img_id))
        _save_image_history(history)

    return save_path


# ──────────────────────────────────────────────────
# Unsplash (고퀄 시네마틱 이미지)
# ──────────────────────────────────────────────────

UNSPLASH_HISTORY_FILE = Path.home() / ".suno_unsplash_history.json"


def _load_unsplash_history() -> set[str]:
    if not UNSPLASH_HISTORY_FILE.exists():
        return set()
    try:
        data = json.loads(UNSPLASH_HISTORY_FILE.read_text(encoding="utf-8"))
        return set(str(x) for x in data)
    except Exception:
        return set()


def _save_unsplash_history(history: set[str]) -> None:
    try:
        kept = sorted(history)[-1000:]
        UNSPLASH_HISTORY_FILE.write_text(json.dumps(kept), encoding="utf-8")
    except Exception:
        pass


def fetch_unsplash_image(keyword: str, access_key: str, save_dir: Path) -> Path | None:
    """
    Unsplash에서 시네마틱 감성 이미지를 다운로드.

    전략:
    1. 한글 키워드 → 영어 동의어 풀에서 랜덤 선택
    2. 감성 모디파이어 추가
    3. per_page=30, orientation=landscape
    4. 랜덤 페이지(1~3)
    5. 이미지 ID 이력 제외
    """
    import urllib.request
    import urllib.parse

    if not access_key:
        return None

    save_dir.mkdir(parents=True, exist_ok=True)
    history = _load_unsplash_history()

    def _search(search_term: str, page: int) -> list[dict]:
        query = urllib.parse.quote(search_term)
        url = (
            f"https://api.unsplash.com/search/photos?query={query}"
            f"&per_page=30&page={page}&orientation=landscape&content_filter=high"
        )
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Client-ID {access_key}",
                "Accept-Version": "v1",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            return data.get("results", [])
        except Exception:
            return []

    chosen = None
    for attempt in range(5):
        simple = attempt >= 3
        search_term = _keyword_to_english(keyword, simple=simple)
        page = random.randint(1, 3)
        hits = _search(search_term, page)

        if not hits:
            hits = _search(search_term, 1)
            if not hits:
                continue

        fresh = [h for h in hits if str(h.get("id")) not in history]

        if fresh:
            chosen = random.choice(fresh)
            break

    if chosen is None:
        hits = _search("cinematic aesthetic landscape", 1)
        if not hits:
            return None
        chosen = random.choice(hits)

    # Unsplash는 urls 안에 다양한 크기 제공: raw/full/regular/small
    urls = chosen.get("urls", {})
    img_url = urls.get("regular") or urls.get("full") or urls.get("raw")
    if not img_url:
        return None

    img_id = str(chosen.get("id", ""))
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in keyword)[:30]
    save_path = save_dir / f"{safe_name}_{img_id}.jpg"

    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": "SunoAutoPlaylist/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            save_path.write_bytes(resp.read())
    except Exception:
        return None

    # Unsplash API 가이드라인: 다운로드 트리거 핑
    download_url = chosen.get("links", {}).get("download_location")
    if download_url:
        try:
            req = urllib.request.Request(download_url, headers={
                "Authorization": f"Client-ID {access_key}",
            })
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:
            pass

    if img_id:
        history.add(img_id)
        _save_unsplash_history(history)

    return save_path
