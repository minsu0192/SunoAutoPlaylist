# SunoAutoPlaylist

수노(Suno) AI에서 음악을 생성하고, MP4로 변환한 뒤 YouTube에 자동 업로드하는 MCP 서버입니다.
Claude Desktop과 연결하면 채팅 한 줄로 전체 파이프라인을 실행할 수 있습니다.

---

## 목차

- [기능](#기능)
- [프로젝트 구조](#프로젝트-구조)
- [사전 준비](#사전-준비)
- [설치](#설치)
- [설정](#설정)
- [실행](#실행)
- [사용 가능한 툴](#사용-가능한-툴)
- [사용 예시](#사용-예시)
- [주의사항](#주의사항)

---

## 기능

| 기능 | 설명 |
|---|---|
| AI 음악 생성 | 수노 웹사이트 자동 조작으로 MP3 다운로드 |
| MP4 변환 | FFmpeg로 MP3 + 커버 이미지 → YouTube용 1080p 영상 |
| 플레이리스트 생성 | 다운로드된 곡들로 M3U 플레이리스트 파일 자동 생성 |
| YouTube 업로드 | YouTube Data API v3로 영상 업로드 및 재생목록 추가 |
| 원클릭 파이프라인 | 생성 → 변환 → 업로드를 한 번에 실행 |

---

## 프로젝트 구조

```
SunoAutoPlaylist/
├── server.py              # MCP 서버 진입점 (툴 정의 및 라우팅)
├── suno.py                # 수노 브라우저 자동화 (Playwright)
├── media_processing.py    # MP3 → MP4 변환 (FFmpeg)
├── playlist.py            # M3U 플레이리스트 생성
├── youtube_upload.py      # YouTube 업로드 (Google API)
├── requirements.txt       # Python 의존성
├── assets/
│   └── default_cover.jpg  # 기본 커버 이미지 (선택)
├── downloads/             # 수노에서 다운로드된 MP3 저장소
├── output/                # 변환된 MP4 저장소
├── suno_session.json      # 수노 로그인 세션 캐시 (자동 생성)
├── client_secrets.json    # Google OAuth 클라이언트 ID (직접 추가)
└── token.json             # YouTube 인증 토큰 (자동 생성)
```

---

## 사전 준비

### 시스템 요구사항

- Python 3.11 이상
- [FFmpeg](https://ffmpeg.org/download.html) 설치 및 PATH 등록
- [Google Chrome](https://www.google.com/chrome/) 또는 Chromium

### Google Cloud / YouTube API 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성
3. **YouTube Data API v3** 활성화
4. **사용자 인증 정보** → OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱 유형)
5. `client_secrets.json` 다운로드 → 프로젝트 루트에 저장

---

## 설치

```bash
# 저장소 클론
git clone https://github.com/minsu0192/sunoautoplaylist.git
cd SunoAutoPlaylist

# 가상환경 생성 (권장)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

---

## 설정

### Claude Desktop에 MCP 서버 등록

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) 또는
`%APPDATA%\Claude\claude_desktop_config.json` (Windows)에 아래 내용을 추가합니다.

```json
{
  "mcpServers": {
    "suno-youtube": {
      "command": "python",
      "args": ["/절대경로/SunoAutoPlaylist/server.py"]
    }
  }
}
```

> `python` 대신 가상환경의 Python 경로를 사용하면 의존성 충돌을 방지할 수 있습니다.
> 예: `"/절대경로/SunoAutoPlaylist/.venv/bin/python"`

---

## 실행

MCP 서버는 Claude Desktop이 자동으로 기동합니다. 직접 테스트하려면:

```bash
python server.py
```

YouTube 최초 실행 시 브라우저 창이 열리며 Google 계정 인증을 요청합니다.
인증 후 `token.json`이 생성되며 이후 자동 로그인됩니다.

---

## 사용 가능한 툴

### `generate_song`
수노에서 AI 음악을 생성하고 MP3로 다운로드합니다.

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `title` | string | O | 곡 제목 |
| `prompt` | string | O | 음악 스타일/분위기 (영어 권장) |
| `style` | string | - | 장르 태그 (예: K-pop, ballad) |
| `count` | integer | - | 생성할 곡 수 (기본값: 2) |

---

### `list_songs`
`downloads/` 폴더에 있는 MP3 목록과 파일 크기를 반환합니다.

---

### `create_video`
MP3 파일과 커버 이미지를 합쳐 1920×1080 MP4 영상을 만듭니다.

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `song_filename` | string | O | 변환할 MP3 파일명 |
| `cover_image` | string | - | 커버 이미지 경로 (없으면 자동 생성) |

---

### `create_playlist`
다운로드된 곡들로 M3U 플레이리스트 파일을 생성합니다.

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `name` | string | O | 플레이리스트 이름 |
| `songs` | array | - | 포함할 파일명 목록 (비우면 전체) |

---

### `upload_to_youtube`
MP4 영상을 YouTube에 업로드합니다.

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `video_path` | string | O | 업로드할 MP4 파일 경로 |
| `title` | string | O | YouTube 영상 제목 |
| `description` | string | - | 영상 설명 |
| `tags` | array | - | 태그 목록 |
| `playlist_id` | string | - | 추가할 재생목록 ID |
| `privacy` | string | - | 공개 설정 (`public` / `unlisted` / `private`) |

---

### `full_pipeline`
수노 생성 → MP4 변환 → YouTube 업로드를 한 번에 실행합니다.

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `title` | string | O | 곡 제목 |
| `prompt` | string | O | 음악 스타일/분위기 |
| `style` | string | - | 장르 태그 |
| `yt_playlist` | string | - | YouTube 재생목록 ID |

---

## 사용 예시

Claude Desktop 채팅창에서 다음과 같이 입력합니다.

```
# 음악 생성만
generate_song 으로 "봄날의 설렘" K-pop 발라드 곡을 만들어줘.
prompt: "romantic spring breeze, soft piano, emotional vocals"

# 전체 파이프라인 한 번에
full_pipeline 으로 "여름 드라이브" 곡을 만들고 YouTube에 올려줘.
prompt: "upbeat summer road trip, electric guitar, catchy chorus"
style: "pop rock"

# 플레이리스트 생성
create_playlist 으로 "내 AI 노래 모음" 플레이리스트를 만들어줘.
```

---

## 주의사항

- **수노 이용약관**: 수노는 자동화 도구 사용을 금지하고 있습니다. 계정 정지 위험이 있으므로 개인 학습 목적으로만 사용하세요.
- **YouTube 할당량**: YouTube Data API는 일일 업로드 할당량이 있습니다. 대량 업로드 시 할당량 초과에 주의하세요.
- **`client_secrets.json`**: 이 파일은 민감 정보를 포함하므로 절대 공개 저장소에 커밋하지 마세요. `.gitignore`에 반드시 추가하세요.
- **`token.json`**: 인증 토큰 파일로, 마찬가지로 공개하지 마세요.

`.gitignore` 권장 항목:
```
client_secrets.json
token.json
suno_session.json
downloads/
output/
.venv/
__pycache__/
```
