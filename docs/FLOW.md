# 전체 파이프라인 흐름

```
이미지 + 키워드
      │
      ▼
┌──────────────┐
│  1. 검증      │  API 키, 학습 파일, 이미지 확인
└──────┬───────┘
       ▼
┌──────────────┐
│  2. YouTube   │  제목/설명/태그 생성 (Claude)
│     정보 생성  │
└──────┬───────┘
       ▼
┌──────────────┐
│  3. 콘텐츠    │  가사+스타일 (보컬) / 설명 (Instrumental)
│     생성      │  → Claude API 호출
└──────┬───────┘
       ▼
┌──────────────────────────────────────┐
│  4. Suno.com 자동화                   │
│                                       │
│  ┌─────────────┐  ┌───────────────┐  │
│  │ 보컬 세션    │  │ Instrumental  │  │
│  │ (Advanced)  │  │ (Simple)      │  │
│  │             │  │               │  │
│  │ 가사 입력    │  │ 설명 입력     │  │
│  │ 스타일 입력  │  │ Instrumental  │  │
│  │ 제목 입력    │  │  토글 ON      │  │
│  │ Create 클릭  │  │ Create 클릭   │  │
│  │ 90초 대기    │  │ 90초 대기     │  │
│  │ 다운로드 ×2  │  │ 다운로드 ×2   │  │
│  └─────────────┘  └───────────────┘  │
│                                       │
│  다운로드 흐름 (공통):                  │
│  ... 클릭 → Download hover → MP3 클릭  │
└──────┬───────────────────────────────┘
       ▼
┌──────────────┐
│  5. 영상 생성  │  MP3 + 이미지 → MP4 (FFmpeg)
│              │  1920×1080, H.264, AAC
└──────┬───────┘
       ▼
┌──────────────┐
│  6. YouTube   │  OAuth 인증 → 업로드 → 플레이리스트 추가
│     업로드    │
└──────────────┘
```

## 파일 구조

| 파일 | 역할 | 참고 문서 |
|------|------|-----------|
| `app.py` | GUI (customtkinter) | - |
| `config.py` | 설정 관리 | [01-config.md](01-config.md) |
| `learn.py` | UI 좌표 학습 | [02-learning.md](02-learning.md) |
| `lyrics_gen.py` | 콘텐츠 생성 | [03-content-gen.md](03-content-gen.md) |
| `suno_bot.py` | 브라우저 자동화 | [04-suno-automation.md](04-suno-automation.md) |
| `media_proc.py` | 영상 생성 | [05-media.md](05-media.md) |
| `yt_upload.py` | YouTube 업로드 | [06-youtube.md](06-youtube.md) |
| `pipeline.py` | 오케스트레이터 | 이 문서 |
| `queue_manager.py` | 작업 큐 관리 | - |

## 세션 계산

- 보컬: `ceil(korean_songs / 2) + ceil(english_songs / 2)` 세션
- Instrumental: `ceil(instrumental_songs / 2)` 세션
- 각 세션 = Suno에서 2곡 동시 생성
- 보컬은 `vocal_pick` 설정에 따라 1~2곡 선택
- Instrumental은 항상 2곡 모두 사용
