# 콘텐츠 생성 (lyrics_gen.py)

모델: `claude-haiku-4-5-20251001`

## 함수

### generate_song_content(keyword, language, index, api_key)

보컬곡 가사 + 스타일 생성.

- **입력**: 키워드, 언어(korean/english), 인덱스(버전), API 키
- **출력**: `{"lyrics": "가사...", "style": "lo-fi, chill, 120 BPM..."}`
- lyrics: 최소 4절, 섹션 레이블([Verse 1], [Chorus] 등)
- style: 영어, 50자 이내, Suno Style 입력칸에 넣을 값

### generate_instrumental_description(keyword, api_key)

Instrumental 곡 Song Description 생성. **프로젝트당 1회 호출.**

- **입력**: 키워드, API 키
- **출력**: 영어 설명 문자열 (200자 이내)
- 분위기, 악기, 템포, 장르를 포함
- 실패 시 키워드 그대로 반환 (fallback)

### generate_youtube_info(keyword, total_songs, api_key)

YouTube 업로드 메타데이터 생성.

- **입력**: 키워드, 총 곡 수, API 키
- **출력**: `{"title": "...", "description": "...", "tags": [...]}`
- title: 50자 이내
- description: 200자 이내, 해시태그 포함
- tags: 최소 8개
