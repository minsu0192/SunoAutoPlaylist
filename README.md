# 수노 자동화 (SunoAutoPlaylist)

이미지 + 키워드 하나로 **Suno AI 음악 생성 → MP4 영상 제작 → YouTube 업로드**까지 완전 자동화하는 개인 맥북 전용 도구.

---

## 전체 워크플로

```
이미지 파일을 ~/SunoProjects/input/ 에 드롭
         ↓
Claude Haiku: 키워드+이미지 → 가사/스타일/설명 자동 생성
         ↓
pyautogui: Chrome에서 Suno 자동 조작 → MP3 다운로드
         ↓
FFmpeg: MP3 + 커버이미지 → MP4
         ↓
YouTube API: 업로드 + 플레이리스트 추가
         ↓
macOS 알림으로 완료 통보
```

---

## 프로젝트 폴더 구조

```
~/SunoProjects/
├── input/                    ← 이미지를 여기에 드롭 (파일명 = 키워드)
│   └── 01_sunset_calm.jpg
├── queue.json                ← 자동 생성 (프로젝트 상태 추적)
└── projects/                 ← 처리된 프로젝트
    └── 2026-04-01_sunset_calm/
        ├── cover.jpg         ← 원본 이미지
        ├── content.json      ← 가사/스타일/설명 (Claude 생성)
        ├── song.mp3          ← 선택된 곡
        ├── song.mp4          ← 완성 영상
        └── status.json       ← 처리 상태

~/.suno_config.json           ← 앱 설정
~/.suno_auto.log              ← 실행 로그
```

**이미지 파일명 규칙:**
- 파일명이 자동으로 키워드가 됨
- `01_sunset_calm.jpg` → 키워드: `sunset calm`
- `도시의 밤.jpg` → 키워드: `도시의 밤`
- 앞쪽 숫자/구분자는 자동 제거됨

---

## A-to-Z 맥북 설치 가이드

### 1단계: 필수 프로그램 설치

```bash
# Homebrew (없으면)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.11 + FFmpeg
brew install python@3.11 ffmpeg

# 확인
python3.11 --version
ffmpeg -version
```

### 2단계: 프로젝트 다운로드

```bash
cd ~
git clone https://github.com/minsu0192/SunoAutoPlaylist.git
cd SunoAutoPlaylist

# 가상환경 생성 및 패키지 설치
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3단계: Anthropic API 키 준비

1. [console.anthropic.com](https://console.anthropic.com) 에서 API 키 발급
2. 앱 실행 후 메뉴 → **⚙️ 설정...** 에서 입력

### 4단계: Chrome에서 Suno 로그인

1. Chrome 브라우저에서 **[suno.com](https://suno.com)** 접속
2. 구글 계정으로 로그인
3. **이후로는 로그인 유지됨** — 앱이 이 Chrome을 제어함

> ⚠️ 로그인은 한 번만 수동으로 하면 됩니다. pyautogui는 실제 Chrome을 조작하므로 Cloudflare 차단 없이 작동합니다.

### 5단계: UI 학습 (최초 1회)

```bash
source .venv/bin/activate
python suno_learn.py
```

- Chrome에서 **https://suno.com/create** 를 열어두기 (Advanced 탭)
- Claude가 각 버튼 위치를 자동으로 학습 → `suno_actions.json` 저장
- Suno UI가 변경되면 재학습 필요 (메뉴 → 🔄 UI 재학습)

### 6단계: 설정

앱 실행 후 메뉴 → **⚙️ 설정...**

| 설정 항목 | 설명 |
|-----------|------|
| Anthropic API 키 | Claude Haiku 사용 (가사 생성, UI 탐지) |
| 프로젝트 폴더 | 기본: ~/SunoProjects |
| 기본 음악 스타일 | Suno 스타일 프롬프트 기본값 |
| 보컬 타입 | 여성/남성/없음 |
| 곡 선택 방식 | 긴 곡 자동/랜덤/수동 |
| 예약 실행 시간 | 예: `02:00` (비우면 예약 없음) |
| YouTube 플레이리스트 ID | YouTube 재생목록에 자동 추가 |
| YouTube 자동 업로드 | 체크 시 MP4 완성 후 자동 업로드 |

### 7단계: 메뉴바 앱 실행

```bash
source .venv/bin/activate
python suno_menu_bar.py
```

상단 메뉴바에 **🎵** 아이콘이 나타남. 터미널 창 닫아도 계속 실행됨.

---

## 사용 방법

### 기본 사용

1. **📂 입력 폴더 열기** 클릭 → Finder 창 열림
2. 준비한 이미지를 `input/` 폴더에 드래그앤드롭
   - 파일명 = 곡 키워드 (한글/영문 모두 가능)
3. **▶ 지금 실행** 클릭 또는 예약 시간 대기
4. macOS 다이얼로그에서 "Chrome에서 suno.com/create 열었습니다" 확인 클릭
5. 자동화 진행 → 완료 알림

### 예약 실행

- **⚙️ 설정...** → 예약 실행 시간 입력 (예: `03:00`)
- 매일 해당 시각에 자동 실행

### 진행 상황 확인

- **📋 로그 보기** 클릭 → 최근 50줄 표시
- `~/.suno_auto.log` 파일 직접 확인

---

## YouTube 연동 설정 (선택)

### 1. Google Cloud Console 설정

1. [console.cloud.google.com](https://console.cloud.google.com) → 새 프로젝트 생성
2. **YouTube Data API v3** 활성화
3. **사용자 인증 정보** → **OAuth 클라이언트 ID** 생성 (유형: 데스크톱 앱)
4. `client_secrets.json` 다운로드 → 프로젝트 폴더(`~/SunoAutoPlaylist/`)에 저장

### 2. 최초 인증

첫 YouTube 업로드 시 브라우저가 열려 Google 로그인 요청.
인증 완료 후 `token.json` 자동 저장 → 이후 자동 갱신.

### 3. 설정

**⚙️ 설정...** → YouTube 섹션에서:
- 자동 업로드 체크
- 플레이리스트 ID 입력 (URL의 `PLxxxxxxx` 부분)
- 공개 범위 선택 (public/unlisted/private)

---

## .app 빌드 (터미널 없이 실행)

```bash
source .venv/bin/activate
bash build_app.sh
```

`dist/수노자동화.app` 생성 → Launchpad에서 실행 가능.

---

## 코드 구조

```
SunoAutoPlaylist/
├── suno_menu_bar.py        ← 메뉴바 앱 진입점 (rumps)
├── suno_pipeline.py        ← 파이프라인 오케스트레이터
├── suno_lyrics_gen.py      ← Claude Haiku: 가사/스타일/설명 생성
├── suno_project_manager.py ← 프로젝트 큐 관리
├── suno_settings.py        ← 설정 창 (tkinter)
├── suno_runner.py          ← Suno pyautogui 자동화
├── suno_learn.py           ← UI 좌표 학습
├── suno_ui_checker.py      ← UI 변경 감지 (3-stage token guard)
├── media_processing.py     ← FFmpeg MP3+이미지 → MP4
├── youtube_upload.py       ← YouTube Data API v3 업로드
├── playlist.py             ← M3U 재생목록 생성
├── server.py               ← MCP 서버 (Claude Desktop 연동)
├── build_app.sh            ← PyInstaller .app 빌드 스크립트
└── requirements.txt
```

---

## 문제 해결

| 증상 | 해결 방법 |
|------|-----------|
| 클릭이 잘못된 위치에 됨 | 메뉴 → 🔄 UI 재학습 |
| MP3 파일을 못 찾음 | ~/Downloads 폴더 확인, 다운로드 완료 후 재시도 |
| YouTube 업로드 실패 | client_secrets.json 존재 여부 확인, OAuth 재인증 |
| API 키 오류 | ⚙️ 설정에서 API 키 재입력 |
| 앱이 멈춤 | 📋 로그 보기로 오류 확인 후 종료 → 재시작 |

> 로그 위치: `~/.suno_auto.log`
