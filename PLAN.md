# Suno Auto Playlist — Architecture Plan

## 개요

이미지를 드래그앤드롭으로 입력하면, Suno.com에서 자동으로 곡을 생성하고, 이미지와 음악을 합쳐 MP4 영상을 만든 뒤 YouTube에 자동 업로드하는 데스크톱 앱.

---

## 파일별 역할

| 파일 | 역할 |
|------|------|
| `app.py` | 메인 GUI (tkinterdnd2). 드래그앤드롭, 큐 목록, 설정 창 |
| `config.py` | 앱 설정 관리 (`~/.suno_auto.json`) |
| `queue_manager.py` | 작업 큐 관리 (`~/.suno_queue.json`) |
| `learn.py` | Suno.com UI 좌표 학습 (pynput + osascript) |
| `lyrics_gen.py` | Claude API로 가사/스타일/YouTube 정보 생성 |
| `suno_bot.py` | pyautogui로 Suno.com 자동 조작 |
| `media_proc.py` | FFmpeg으로 MP3 + 이미지 → MP4 변환 |
| `yt_upload.py` | YouTube Data API v3로 업로드 |
| `pipeline.py` | 전체 파이프라인 오케스트레이터 |
| `requirements.txt` | Python 패키지 의존성 |
| `build.sh` | PyInstaller 빌드 스크립트 |

---

## 실행 흐름

```
사용자가 이미지 드래그앤드롭 + 키워드 입력
        │
        ▼
[app.py] QueueManager.add(image_path, keyword)
        │
        ▼
사용자가 "지금 실행" 버튼 클릭
        │
        ▼
[pipeline.py] Pipeline.run(queue_item)
        │
        ├─ [1] 검증
        │       - Anthropic API 키 확인
        │       - ~/.suno_actions.json 존재 확인
        │       - 이미지 파일 존재 확인
        │
        ├─ [2] YouTube 정보 생성 (1회)
        │       lyrics_gen.generate_youtube_info(keyword, total_songs, api_key)
        │       → {title, description, tags}
        │
        ├─ [3] 곡별 가사/스타일 생성
        │       korean_songs개: generate_song_content(keyword, "korean", i, api_key)
        │       english_songs개: generate_song_content(keyword, "english", i, api_key)
        │       → list of {lyrics, style, language}
        │
        ├─ [4] Suno 세션 반복 (ceil(total_songs/2) 회)
        │       2곡씩 묶어서 suno_bot.run_suno_session() 호출
        │       → 다운받은 MP3 파일 목록 누적
        │
        ├─ [5] 영상 생성
        │       output_dir / keyword / 폴더 생성
        │       각 MP3마다 media_proc.make_video(mp3, image, output) 호출
        │       → MP4 파일 목록
        │
        └─ [6] YouTube 업로드
                각 MP4마다 yt_upload.YouTubeUploader.upload() 호출
                playlist_id로 플레이리스트에 추가
                → YouTube URL 반환
```

---

## UI 좌표 학습 흐름 (learn.py)

```
[1단계 대화창] → 학습 시작 클릭
        │
        ▼
pynput 키보드 리스너 시작
숫자키 1~5: Advanced 탭, 가사 입력창, 스타일 입력창, 제목 입력창, Create 버튼 좌표 저장
각 키 누를 때마다 osascript notification으로 확인 메시지
        │
        ▼
[2단계 대화창] → 완료 클릭
        │
        ▼
숫자키 6~7: ... 버튼, Download 메뉴 좌표 저장
        │
        ▼
~/.suno_actions.json 저장
[완료 대화창]
```

---

## 데이터 구조

### Queue Item
```json
{
  "id": "uuid",
  "image_path": "/path/to/image.png",
  "keyword": "lofi chill",
  "status": "pending|processing|done|failed",
  "created_at": "ISO8601",
  "error": null
}
```

### Config (~/.suno_auto.json)
```json
{
  "anthropic_api_key": "",
  "korean_songs": 3,
  "english_songs": 3,
  "youtube_client_secrets": "",
  "youtube_playlist_id": "",
  "youtube_privacy": "public",
  "output_dir": "~/SunoOutput"
}
```

### Actions (~/.suno_actions.json)
```json
{
  "advanced_tab": [x, y],
  "lyrics_input": [x, y],
  "style_input": [x, y],
  "title_input": [x, y],
  "create_btn": [x, y],
  "song_dot_btn": [x, y],
  "download_item": [x, y]
}
```

---

## 의존성

- **anthropic** — Claude API (가사/스타일 생성)
- **pyautogui** — GUI 자동화 (마우스 클릭, 키 입력)
- **pyperclip** — 클립보드 (한글 입력 안정성)
- **pynput** — 키보드/마우스 이벤트 감지 (좌표 학습)
- **Pillow** — 이미지 처리
- **tkinterdnd2** — 드래그앤드롭 지원 Tkinter
- **google-api-python-client** — YouTube API
- **google-auth-oauthlib** — YouTube OAuth

---

## 빌드

```bash
chmod +x build.sh
./build.sh
```

결과: `dist/수노자동화.app`
