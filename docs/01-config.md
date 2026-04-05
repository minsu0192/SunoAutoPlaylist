# 설정 (config.py)

파일 위치: `~/.suno_auto.json`

## 설정 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `anthropic_api_key` | str | `""` | Claude API 키 (필수) |
| `korean_songs` | int | `3` | 한국어 보컬곡 수 |
| `english_songs` | int | `3` | 영어 보컬곡 수 |
| `instrumental_songs` | int | `0` | Instrumental 곡 수 |
| `vocal_pick` | str | `"longer"` | 보컬곡 선택: longer/shorter/both |
| `youtube_client_secrets` | str | `""` | YouTube OAuth JSON 경로 |
| `youtube_playlist_id` | str | `""` | YouTube 플레이리스트 ID |
| `youtube_privacy` | str | `"public"` | 공개범위: public/unlisted/private |
| `output_dir` | str | `~/SunoOutput` | 출력 폴더 |

## vocal_pick 옵션

Suno는 한 세션에 2곡을 생성함. 보컬곡은 같은 가사에 다른 편곡이므로:

- `longer` — 파일 크기가 더 큰 곡 1개 선택 (나머지 삭제)
- `shorter` — 파일 크기가 더 작은 곡 1개 선택
- `both` — 2곡 모두 사용

Instrumental은 항상 2곡 모두 사용 (가사가 없으므로 둘 다 고유).
