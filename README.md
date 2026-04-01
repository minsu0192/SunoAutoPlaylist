# SunoAutoPlaylist

Suno AI로 음악을 생성하고, MP4로 변환한 뒤 YouTube에 자동 업로드하는 자동화 도구입니다.  
웹앱 UI, 로컬 백엔드 자동화, Claude Desktop MCP 연동 세 가지 방식을 지원합니다.

---

## 목차

- [전체 구성 한눈에 보기](#전체-구성-한눈에-보기)
- [프로젝트 구조](#프로젝트-구조)
- [사전 준비](#사전-준비)
- [설치](#설치)
- [API 키 관리](#api-키-관리)
- [사용 방법](#사용-방법)
  - [모드 A: 웹앱 + 로컬 백엔드](#모드-a-웹앱--로컬-백엔드-일반-사용)
  - [모드 B: pyautogui 준자동화](#모드-b-pyautogui-준자동화-suno-직접-조작)
  - [모드 C: Claude Desktop MCP](#모드-c-claude-desktop-mcp-연동)
- [Cloudflare Pages 배포](#cloudflare-pages-배포)
- [MCP 툴 명세](#mcp-툴-명세)
- [주의사항](#주의사항)

---

## 전체 구성 한눈에 보기

```
[웹앱 - Cloudflare Pages]          [로컬 맥북]
Seoul Diary Playlist Generator  →  FastAPI (api.py)  →  Suno 자동화
       ↓ 무드 선택·프롬프트 생성         ↓ 음악 생성 요청      ↓ pyautogui 마우스 조작
       ↓ YouTube 메타데이터 생성         ↓ MP3 다운로드        ↓ MP3 → MP4 변환
                                         ↓ YouTube 업로드
```

| 구성 요소 | 기술 스택 | 역할 |
|-----------|-----------|------|
| 웹앱 | React + Firebase + Cloudflare Pages | 무드 선택, 프롬프트/메타데이터 생성 UI |
| 로컬 백엔드 | FastAPI + Python 3.11 | Suno 자동화, MP4 변환, YouTube 업로드 |
| Suno 자동화 | pyautogui + Claude Vision | UI 좌표 학습 후 마우스 자동 조작 |
| MCP 서버 | mcp + Claude Desktop | 채팅 한 줄로 전체 파이프라인 실행 |

> **웹앱 배포판**은 프롬프트·메타데이터 생성만 가능합니다.  
> Suno 자동화·YouTube 업로드는 **로컬 맥북**에서만 실행됩니다.

---

## 프로젝트 구조

```
SunoAutoPlaylist/
├── server.py               # MCP 서버 (Claude Desktop 연동)
├── api.py                  # FastAPI REST 서버 (웹앱 연동)
├── suno.py                 # Suno 브라우저 자동화 (Playwright 기반)
├── suno_learn.py           # Claude Vision으로 Suno UI 좌표 자동 학습
├── suno_runner.py          # 학습된 좌표로 pyautogui 자동 조작
├── suno_login.py           # Suno 최초 로그인 세션 저장 (일회성)
├── media_processing.py     # MP3 → MP4 변환 (FFmpeg)
├── playlist.py             # M3U 플레이리스트 생성
├── youtube_upload.py       # YouTube Data API v3 업로드
├── requirements.txt        # Python 의존성
├── .env                    # API 키 환경변수 (gitignore, 직접 생성)
├── frontend/               # React 웹앱
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js          # FastAPI 클라이언트 (X-Anthropic-Api-Key 헤더)
│   │   ├── firebase.js     # Firebase 인증 설정
│   │   ├── components/
│   │   │   ├── Login.jsx
│   │   │   ├── AuthWrapper.jsx
│   │   │   ├── ResultPanel.jsx
│   │   │   └── ApiKeySettings.jsx  # 사용자별 API 키 입력 모달
│   │   └── data/
│   │       └── moods.js    # 무드 프리셋 (indie/seasonal/lofi)
│   └── package.json
├── assets/
│   └── default_cover.jpg   # 기본 커버 이미지 (선택)
├── downloads/              # 다운로드된 MP3 저장소 (자동 생성)
├── output/                 # 변환된 MP4 저장소 (자동 생성)
├── client_secrets.json     # Google OAuth 클라이언트 ID (직접 추가)
└── token.json              # YouTube 인증 토큰 (자동 생성)
```

**gitignore 처리된 파일** (절대 커밋 금지):
- `.env` — API 키
- `suno_actions.json` — 학습된 UI 좌표
- `client_secrets.json`, `token.json` — Google 인증 정보

---

## 사전 준비

### 시스템 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| Python | 3.11 이상 | mcp 패키지 호환성 필수 |
| Node.js | 18 이상 | 프론트엔드 빌드 |
| Google Chrome | 최신 | Suno 자동화 |
| FFmpeg | 최신 | MP3→MP4 변환 |

**FFmpeg 설치 (macOS):**
```bash
brew install ffmpeg
```

### Google Cloud / YouTube API 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성
3. **YouTube Data API v3** 활성화
4. **사용자 인증 정보** → OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱 유형)
5. `client_secrets.json` 다운로드 → 프로젝트 루트에 저장

### Firebase 설정 (웹앱 Google 로그인)

1. [Firebase Console](https://console.firebase.google.com/) → 프로젝트 생성
2. Authentication → Google 로그인 활성화
3. **Authentication → Settings → Authorized domains**에 배포 도메인 추가
4. `frontend/src/firebase.js`에 프로젝트 config 입력

---

## 설치

```bash
# 저장소 클론
git clone https://github.com/minsu0192/sunoautoplaylist.git
cd SunoAutoPlaylist

# Python 패키지 설치 (Python 3.11 필수)
pip3.11 install -r requirements.txt

# 준자동화 추가 패키지
pip3.11 install pyautogui pillow anthropic

# Playwright 브라우저 설치
python3.11 -m playwright install chromium

# 프론트엔드 의존성 설치
cd frontend && npm install && cd ..
```

---

## API 키 관리

### 로컬 백엔드용 (.env 파일)

```bash
# .env 파일 생성 (터미널 히스토리에 남지 않음)
echo "ANTHROPIC_API_KEY=sk-ant-여기에키입력" > .env

# 본인만 읽을 수 있도록 권한 제한
chmod 600 .env
```

`.env`는 `.gitignore`에 등록되어 있어 깃허브에 절대 올라가지 않습니다.

### 웹앱 사용자용 (브라우저 localStorage)

웹앱 헤더의 **⚙️ API 키 설정** 버튼 → API 키 입력  
- 브라우저 localStorage에만 저장 (서버 미전송)  
- 각 사용자가 본인 Anthropic 계정 비용 부담  
- Spending Limit 설정 권장: [Anthropic Console](https://console.anthropic.com/)

---

## 사용 방법

### 모드 A: 웹앱 + 로컬 백엔드 (일반 사용)

**1단계 — API 서버 실행** (터미널 1)
```bash
cd ~/SunoAutoPlaylist
python3.11 api.py
```
`Uvicorn running on http://0.0.0.0:8000` 확인

**2단계 — 웹앱 실행** (터미널 2, ⌘T 새 탭)
```bash
cd ~/SunoAutoPlaylist/frontend
npm start
```
브라우저에서 `http://localhost:3000` 자동 오픈

**3단계 — 사용**
1. Google 계정으로 로그인
2. 헤더 ⚙️ → Anthropic API 키 입력
3. 무드 카드 선택 (indie / seasonal / lofi)
4. 생성된 프롬프트·메타데이터 확인
5. **▶ 실행 (Suno 음악 생성)** 버튼 클릭

> 두 터미널이 동시에 켜져 있어야 실행 버튼이 작동합니다.

---

### 모드 B: pyautogui 준자동화 (Suno 직접 조작)

Playwright 브라우저 대신 **실제 마우스를 조작**해 Cloudflare 차단을 우회합니다.

#### 최초 학습 (처음 한 번 + UI 변경 시)

```bash
python3.11 suno_learn.py
```

1. 크롬에서 `https://suno.com/create` 접속 후 Custom Mode 활성화
2. 스크립트가 화면을 캡처 → Claude Vision이 버튼 위치 자동 감지
3. 각 요소마다 "올바른 위치인가요? (y/n)" 확인
4. 틀리면 직접 마우스로 클릭해 수동 보정
5. `suno_actions.json`에 저장

#### 자동 실행

```bash
# 대화형 입력
python3.11 suno_runner.py

# 또는 파라미터 직접 지정
python3.11 suno_runner.py --title "로파이 카페" --prompt "lofi hip hop, chill beats" --style "lofi"
```

> ⚠️ 마우스를 화면 왼쪽 상단 모서리로 이동하면 즉시 중단됩니다 (안전 장치).

#### UI 변경 시 재학습

수노 UI가 바뀌어서 클릭이 안 되면:
```bash
python3.11 suno_learn.py   # 재학습
python3.11 suno_runner.py  # 다시 실행
```

---

### 모드 C: Claude Desktop MCP 연동

Claude Desktop 채팅창에서 자연어로 전체 파이프라인을 실행합니다.

**설정 파일 위치:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "suno-youtube": {
      "command": "/opt/homebrew/bin/python3.11",
      "args": ["/절대경로/SunoAutoPlaylist/server.py"]
    }
  }
}
```

**사용 예:**
```
generate_song 으로 "봄날의 설렘" K-pop 발라드 곡을 만들어줘.
prompt: "romantic spring breeze, soft piano, emotional vocals"

full_pipeline 으로 "여름 드라이브" 곡을 만들고 YouTube에 올려줘.
prompt: "upbeat summer road trip, electric guitar, catchy chorus"
style: "pop rock"
```

---

## Cloudflare Pages 배포

```bash
# 프로젝트 설정
빌드 명령: CI=false react-scripts build
빌드 출력 디렉토리: build
루트 디렉토리: frontend
```

**배포 후 체크리스트:**
- [ ] Firebase Console → Authentication → Authorized domains에 `*.pages.dev` 추가
- [ ] `frontend/.env`에 `REACT_APP_API_URL=http://localhost:8000` 설정 확인

> 배포판(https)에서 로컬 API(http)를 호출하면 Mixed Content 오류가 납니다.  
> 배포판은 프롬프트·메타데이터 생성 용도로만 사용하고,  
> Suno 자동화는 `npm start`로 로컬에서 실행하세요.

---

## MCP 툴 명세

### `generate_song`
Suno에서 AI 음악 생성 후 MP3 다운로드

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `title` | string | ✅ | 곡 제목 |
| `prompt` | string | ✅ | 음악 스타일/분위기 (영어 권장) |
| `style` | string | | 장르 태그 (예: lofi, K-pop) |
| `count` | integer | | 생성할 곡 수 (기본값: 2) |

### `list_songs`
`downloads/` 폴더의 MP3 목록과 파일 크기 반환

### `create_video`
MP3 + 커버 이미지 → 1920×1080 MP4 변환

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `song_filename` | string | ✅ | 변환할 MP3 파일명 |
| `cover_image` | string | | 커버 이미지 경로 (없으면 자동 생성) |

### `create_playlist`
다운로드된 곡들로 M3U 플레이리스트 생성

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `name` | string | ✅ | 플레이리스트 이름 |
| `songs` | array | | 포함할 파일명 목록 (비우면 전체) |

### `upload_to_youtube`
MP4 영상을 YouTube에 업로드

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `video_path` | string | ✅ | 업로드할 MP4 경로 |
| `title` | string | ✅ | YouTube 영상 제목 |
| `description` | string | | 영상 설명 |
| `tags` | array | | 태그 목록 |
| `playlist_id` | string | | 추가할 재생목록 ID |
| `privacy` | string | | `public` / `unlisted` / `private` |

### `full_pipeline`
생성 → 변환 → 업로드 한 번에 실행

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `title` | string | ✅ | 곡 제목 |
| `prompt` | string | ✅ | 음악 스타일/분위기 |
| `style` | string | | 장르 태그 |
| `yt_playlist` | string | | YouTube 재생목록 ID |

---

## 주의사항

- **Suno 이용약관**: 자동화 도구 사용을 금지하고 있습니다. 개인 학습 목적으로만 사용하세요.
- **API 키 보안**: `.env`, `client_secrets.json`, `token.json`은 절대 깃허브에 커밋하지 마세요.
- **YouTube 할당량**: YouTube Data API는 일일 업로드 할당량이 있습니다. 대량 업로드 시 주의하세요.
- **비용**: Anthropic API는 사용량에 따라 요금이 부과됩니다. [Spending Limit](https://console.anthropic.com/) 설정을 권장합니다.
- **로컬 전용**: Suno 자동화와 YouTube 업로드는 맥북 로컬 환경에서만 실행 가능합니다.
