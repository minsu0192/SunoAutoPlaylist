# SunoAuto DASH v1.3.2

키워드 입력 하나로 AI 작곡 + 영상 제작 + YouTube 업로드까지 자동화하는 macOS 데스크탑 앱

---

## 전체 흐름

```
키워드 입력 (예: "새벽 감성 lofi")
      |
      v
[1] Claude API — 가사 + 스타일 + 곡 제목 자동 생성
      |
      v
[2] Suno.com 자동 조작 (pyautogui)
    — 가사/스타일/제목 입력 → Create → 대기 → MP3 다운로드
      |
      v
[3] FFmpeg — MP3 + 배경이미지 → MP4 영상 생성
      |
      v
[4] YouTube Data API — 자동 업로드 (감성 제목 + 설명 + 태그)
```

---

## 주요 기능

- **사이드바 UI** — 작업 생성 / 설정 관리 / 실행 로그 페이지
- **큐 시스템** — 키워드를 여러 개 등록하고 순차 실행
- **Claude 가사 생성** — 한국어/영어/인스트루멘탈 곡 자동 작사
- **스냅샷 기반 다운로드 감지** — 기존 파일을 건드리지 않고 새 파일만 정확히 추적
- **Chrome 프로필 자동 감지** — 활성 프로필의 다운로드 경로를 자동으로 찾음
- **Pixabay 이미지** — 키워드 기반 배경 이미지 자동 검색
- **FFmpeg 영상 생성** — 정지 이미지 + MP3 합성, stillimage 최적화로 빠른 인코딩
- **YouTube 자동 업로드** — 플레이리스트 추가, 공개 상태 설정

---

## 설치

### 필수 요구사항

- macOS
- Python 3.11+
- Google Chrome
- FFmpeg (`brew install ffmpeg`)

### 설치 방법

```bash
git clone https://github.com/minsu0192/SunoAutoPlaylist.git
cd SunoAutoPlaylist

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# FFmpeg 설치 (영상 생성에 필요)
brew install ffmpeg
```

---

## 실행

```bash
source .venv/bin/activate
python app.py
```

---

## 최초 설정

### 1. API 키 입력
앱 실행 후 **설정 관리** 페이지에서:
- **Anthropic API Key** — [console.anthropic.com](https://console.anthropic.com) 에서 발급
- **Pixabay API Key** (선택) — 배경 이미지 자동 검색용

### 2. UI 학습 (1회 필수)
사이드바 하단 **UI 학습하기** 클릭

```
Chrome에서 suno.com/create 열고 Advanced 탭을 연 상태에서:

[1] Advanced 탭
[2] Lyrics 입력창
[3] Styles 입력창
[4] Song Title 입력창
[5] Create 버튼
[6] 생성된 곡의 ... 버튼 (첫째/둘째 각각)
[7] Download → MP3 버튼 (첫째/둘째 각각)
```

### 3. YouTube 연동 (선택)
설정 관리 페이지에서:
1. `client_secrets.json` 파일 선택 (Google Cloud Console에서 다운로드)
2. **Google 계정 인증하기** 클릭
3. Playlist ID, 공개 상태 설정

> Google Cloud Console에서 YouTube Data API v3 활성화 + OAuth 2.0 클라이언트(데스크톱 앱) 생성 필요

---

## 사용법

1. **작업 생성** 페이지에서 키워드 입력 또는 이미지 드래그
2. **실행** 버튼 클릭
3. Chrome에서 suno.com 로그인 상태 유지
4. 자동으로 곡 생성 → 다운로드 → 영상 제작 → 업로드

---

## 설정 옵션

| 항목 | 설명 | 기본값 |
|------|------|--------|
| 곡 수 (KR/EN/Inst) | 한국어/영어/인스트루멘탈 곡 수 | 3/3/0 |
| 보컬 선택 | longer/shorter/random/both | longer |
| 실행 범위 | songs/videos/upload | songs |
| 저장 경로 | 결과물 저장 위치 | ~/SunoOutput |

### 실행 범위별 동작

| 범위 | 동작 |
|------|------|
| `songs` | 곡 생성 + 다운로드만 (결과: `~/SunoOutput/completed/`) |
| `videos` | 곡 + 배경이미지 합성 MP4 생성 (결과: `~/SunoOutput/키워드/`) |
| `upload` | 곡 + 영상 + YouTube 자동 업로드 |

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `app.py` | GUI 메인 (사이드바 + 페이지 레이아웃) |
| `config.py` | 설정 관리 (~/.suno_auto.json) |
| `pipeline.py` | 전체 파이프라인 오케스트레이션 |
| `suno_bot.py` | Suno.com 마우스/키보드 자동화 + 다운로드 감지 |
| `learn.py` | UI 좌표 학습 |
| `lyrics_gen.py` | Claude API 가사/스타일/YouTube 정보 생성 |
| `media_proc.py` | FFmpeg 썸네일 + MP4 영상 생성 |
| `queue_manager.py` | 작업 큐 관리 |
| `yt_upload.py` | YouTube 업로드 |
| `youtube_analytics.py` | YouTube 성과 분석 |

### 출력 폴더 구조

```
~/SunoOutput/
  completed/          — 다운로드된 MP3 (모든 세션)
  images/             — Pixabay 배경 이미지
  키워드이름/          — 영상 + 썸네일 (videos/upload scope)
    thumbnail.jpg
    키워드이름.mp4
```

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| 접근성 권한 오류 | 시스템 설정 → 개인정보 → 접근성 → 앱 추가 |
| 마우스가 안 움직임 | 접근성 권한 삭제 후 재추가, 앱 재시작 |
| 다운로드 감지 안 됨 | Chrome 활성 프로필 확인 (로그에 표시됨) |
| ffmpeg을 찾을 수 없음 | `brew install ffmpeg` 실행 |
| 영상 생성 느림 | ffmpeg v8+ 권장, ultrafast + stillimage 프리셋 사용 중 |
| API 인증 실패 | 설정에서 API 키 재입력 |
| YouTube 인증 실패 | client_secrets.json 경로 확인 |
| 폴더를 찾을 수 없음 | scope=songs이면 ~/SunoOutput/completed/ 에 저장됨 |

---

## .app 빌드

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller 수노자동화.spec --noconfirm
# dist/수노자동화.app → Applications 폴더로 이동
```

빌드 후:
1. `dist/수노자동화.app`을 Applications 폴더로 복사
2. 시스템 설정 → 개인정보 → 접근성에서 앱 추가
3. 앱 업데이트 시마다 접근성 권한 재설정 필요

---

## 변경 이력

### v1.3.2
- FFmpeg 경로 자동 탐색 (`/opt/homebrew/bin` 등 .app 번들 대응)
- 영상 인코딩 속도 개선 (`-tune stillimage -preset ultrafast`)

### v1.3.1
- 불필요한 스크롤 코드 제거 (오작동 방지)
- completed 폴더 경로 고정 (`~/SunoOutput/completed/`)
- 파일명 timestamp 충돌 방지

### v1.3.0
- Chrome 활성 프로필 자동 감지 (Local State 기반)
- 스냅샷 비교 방식으로 다운로드 감지 (기존 파일 삭제 안 함)
- `~/Downloads` 파일 보호 (폴더 전체 삭제 제거)

### v1.2.x
- 다운로드 감시 폴더 오류 수정
- UI 좌표 학습 시스템
- 큐 기반 작업 관리
