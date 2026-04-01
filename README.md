# SunoAutoPlaylist — 맥북 실행 가이드 (A to Z)

수노(Suno)에서 AI 음악을 자동 생성·다운로드하고, YouTube에 업로드하는 자동화 도구입니다.

---

## 목차

1. [시스템 준비물](#1-시스템-준비물)
2. [저장소 클론](#2-저장소-클론)
3. [Python 환경 설정](#3-python-환경-설정)
4. [Anthropic API 키 설정](#4-anthropic-api-키-설정)
5. [수노 로그인 세션 저장](#5-수노-로그인-세션-저장)
6. [첫 UI 학습 (suno_learn.py)](#6-첫-ui-학습-suno_learnpy)
7. [자동 실행 (suno_runner.py)](#7-자동-실행-suno_runnerpy)
8. [웹 UI 실행 (선택)](#8-웹-ui-실행-선택)
9. [맥OS 권한 설정](#9-macos-권한-설정)
10. [폴더 구조](#10-폴더-구조)
11. [자주 묻는 문제](#11-자주-묻는-문제)

---

## 1. 시스템 준비물

아래 항목을 순서대로 설치해주세요.

### Python 3.11

```bash
# Homebrew로 설치 (Homebrew가 없으면 먼저 설치)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install python@3.11
```

설치 확인:
```bash
python3.11 --version
# Python 3.11.x
```

### Google Chrome

- 이미 설치되어 있으면 건너뜁니다.
- [chrome.google.com](https://www.google.com/chrome/) 에서 다운로드

### FFmpeg (음악→영상 변환용)

```bash
brew install ffmpeg
```

설치 확인:
```bash
ffmpeg -version
```

### Node.js 18+ (웹 UI 사용 시에만 필요)

```bash
brew install node
```

---

## 2. 저장소 클론

```bash
# 원하는 위치로 이동 (예: 바탕화면)
cd ~/Desktop

# 클론
git clone https://github.com/minsu0192/SunoAutoPlaylist.git
cd SunoAutoPlaylist

# 최신 브랜치로 전환
git checkout claude/suno-playlist-maker-jixsq
git pull origin claude/suno-playlist-maker-jixsq
```

---

## 3. Python 환경 설정

```bash
# 프로젝트 폴더 안에서 실행
cd ~/Desktop/SunoAutoPlaylist

# 가상환경 생성
python3.11 -m venv .venv

# 가상환경 활성화 (터미널을 새로 열 때마다 실행 필요)
source .venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

> ⚠️ 이후 모든 `python` 명령어는 가상환경이 활성화된 상태에서 실행하세요.
> 터미널 프롬프트 앞에 `(.venv)` 가 붙어 있으면 활성화된 상태입니다.

---

## 4. Anthropic API 키 설정

Anthropic API 키가 있어야 Claude Haiku로 UI 좌표 탐지 및 다운로드 자동화가 동작합니다.

### .env 파일 생성

프로젝트 루트에 `.env` 파일을 만들어 API 키를 저장합니다.

```bash
# 프로젝트 폴더 안에서 실행
echo 'ANTHROPIC_API_KEY=여기에_실제_키를_입력' > .env
```

또는 텍스트 편집기로 `.env` 파일을 직접 생성:

```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxx
```

> ✅ `.env` 파일은 `.gitignore`에 등록되어 있어 GitHub에 올라가지 않습니다.

### 환경변수 로드

터미널을 열 때마다 아래 명령어로 API 키를 불러옵니다:

```bash
export $(cat .env | xargs)
```

매번 입력하기 번거로우면 `~/.zshrc`에 추가:

```bash
echo 'export ANTHROPIC_API_KEY=여기에_실제_키를_입력' >> ~/.zshrc
source ~/.zshrc
```

---

## 5. 수노 로그인 확인

> ✅ **별도 로그인 자동화가 없습니다** — 이게 이 방식의 핵심입니다.

이전에 문제가 됐던 "자동 로그인" (Playwright가 Chrome을 열어서 로그인 시도)은
**완전히 제거됐습니다.** Cloudflare 차단, Google OAuth 거부, SMS 인증 미도착 등의
문제가 모두 여기서 비롯됐었습니다.

### 현재 방식 (pyautogui)

```
사용자가 직접 Chrome을 열고 → 직접 로그인 → suno.com/create 이동
    ↓
suno_runner.py 실행 → "준비 완료 후 Enter" 대기
    ↓
Enter 누르면 pyautogui가 마우스만 대신 움직임
```

Suno 입장에서는 **사람이 마우스를 움직이는 것과 구분할 수 없습니다.**
브라우저를 건드리지 않으므로 차단 없음.

### 로그인 방법

1. **평소처럼 Chrome을 엽니다.**
2. **[suno.com](https://suno.com) 에 직접 로그인합니다.**
   - 전화번호, Google, Discord 등 어떤 방법이든 가능
   - 한 번 로그인하면 Chrome 세션이 유지되므로 매번 할 필요 없음
3. **[suno.com/create](https://suno.com/create) 로 이동합니다.**
4. `suno_runner.py` 를 실행하면 Enter를 기다립니다.

> Chrome이 이미 Suno에 로그인된 상태라면 2~3번은 건너뛰어도 됩니다.

---

## 6. 첫 UI 학습 (suno_learn.py)

수노의 버튼·입력란 위치를 Claude Vision API로 자동 학습합니다.
**처음 한 번만 실행하면 됩니다.** 이후에는 UI 변경이 감지될 때만 재실행합니다.

### 사전 준비

1. Chrome에서 **[suno.com/create](https://suno.com/create)** 를 엽니다.
2. 상단 탭에서 **Advanced** 를 클릭합니다.
   ```
   탭 순서: 10s | Simple | Advanced | Sounds
                          ↑ 이걸 클릭
   ```
3. Lyrics, Styles 입력폼이 보이는 상태로 둡니다.

### 실행

```bash
source .venv/bin/activate
export $(cat .env | xargs)

python suno_learn.py
```

- Claude가 화면을 분석해서 각 버튼 위치를 자동으로 찾습니다.
- 찾은 위치가 맞으면 `y`, 틀리면 `n` 입력 후 직접 클릭합니다.
- 완료되면 `suno_actions.json` 파일이 생성됩니다.

> **강제 재학습이 필요한 경우:**
> ```bash
> python suno_learn.py --force
> ```

---

## 7. 자동 실행 (suno_runner.py)

학습이 완료되면 아래 명령어로 수노 자동화를 실행합니다.

### 기본 실행

```bash
source .venv/bin/activate
export $(cat .env | xargs)

python suno_runner.py
```

대화형으로 제목·가사·스타일을 입력하라고 나타납니다.

### 인자로 바로 실행

```bash
python suno_runner.py \
  --title "서울 봄날 감성" \
  --prompt "벚꽃 흩날리는 한강변, 설레는 봄날 오후, 포근한 기억" \
  --style "lofi K-pop chill piano acoustic"
```

### 곡 선택 방식 (--select)

수노는 Create 1회당 같은 스타일의 곡을 **2곡** 생성합니다.
`--select` 옵션으로 어떻게 처리할지 선택하세요:

| 옵션 | 동작 | 다운로드 수 |
|------|------|------------|
| `--select manual` | 2곡 모두 보존, 직접 들어보고 선택 (기본값) | 2곡 |
| `--select random` | 1곡을 랜덤으로 다운로드 | 1곡 |
| `--select longest` | 2곡 중 파일 크기가 큰 곡(=긴 곡) 자동 선택 | 2곡 다운 후 1곡 보존 |

```bash
# 예시: 긴 곡 자동 선택
python suno_runner.py \
  --title "서울 봄날 감성" \
  --prompt "벚꽃 흩날리는 한강변" \
  --style "lofi chill" \
  --select longest
```

### 실행 흐름 (9단계)

```
[1/9] Advanced 탭 클릭
[2/9] 가사(Lyrics) 입력
[3/9] 스타일(Styles) 입력
[4/9] 스크롤 다운 (Song Title / Create 버튼 노출)
[5/9] Song Title 입력
[6/9] Create 버튼 클릭
[7/9] 음악 생성 대기 (~100초, 프로그레스 바 표시)
[8/9] Claude Haiku로 ⋮ 버튼 탐지 → Download → MP3 Audio
[9/9] ~/Downloads MP3 → raw_data/{날짜}_{제목}/ 폴더 이동
```

### 다운로드 결과물

```
raw_data/
  2026-04-01_서울_봄날_감성/
    song_A.mp3           ← 선택된 곡
  _should_delete/
    song_B.mp3           ← 미선택 곡 (직접 확인 후 삭제)
```

> ⚠️ 실행 중 마우스를 **화면 왼쪽 상단 모서리**로 이동하면 즉시 중단됩니다 (안전 장치).

---

## 8. 웹 UI 실행 (선택)

터미널 대신 브라우저에서 조작하고 싶을 때 사용합니다.

### 백엔드 API 서버 실행

```bash
# 터미널 1
cd ~/Desktop/SunoAutoPlaylist
source .venv/bin/activate
export $(cat .env | xargs)
python api.py
# → http://localhost:8000 에서 실행
```

### 프론트엔드 실행

```bash
# 터미널 2
cd ~/Desktop/SunoAutoPlaylist/frontend
npm install          # 처음 한 번만
npm start
# → http://localhost:3000 에서 실행
```

브라우저에서 `http://localhost:3000` 으로 접속합니다.

> ℹ️ 처음 접속 시 Google 로그인이 필요합니다 (Firebase Auth).
> ⚙️ API 키 설정 버튼에서 Anthropic API 키를 입력해두면 웹 UI에서도 자동 탐지가 동작합니다.

---

## 9. macOS 권한 설정

pyautogui가 마우스를 제어하고 화면을 캡처하려면 macOS 보안 권한이 필요합니다.
**최초 실행 시 아래 두 가지를 허용해야 합니다.**

### 접근성 (Accessibility) 권한

> 마우스 클릭·키보드 입력 자동화에 필요

1. **시스템 환경설정** → **개인 정보 보호 및 보안** → **접근성**
2. 목록에서 **터미널** (또는 iTerm2) 을 찾아 **체크 표시** 활성화
3. 없으면 `+` 버튼으로 추가

### 화면 녹화 (Screen Recording) 권한

> 스크린샷 캡처에 필요

1. **시스템 환경설정** → **개인 정보 보호 및 보안** → **화면 녹화**
2. **터미널** (또는 iTerm2) 을 찾아 **체크 표시** 활성화
3. 없으면 `+` 버튼으로 추가

> 권한 변경 후 터미널을 **완전히 종료 후 재시작**해야 적용됩니다.

---

## 10. 폴더 구조

```
SunoAutoPlaylist/
├── suno_runner.py        ← 자동 실행 메인 스크립트
├── suno_learn.py         ← UI 좌표 자동 학습
├── suno_ui_checker.py    ← 시작 시 UI 변경 감지 (토큰 최소화)
├── suno_login.py         ← 수노 로그인 세션 저장 (최초 1회)
├── api.py                ← 웹 UI용 FastAPI 백엔드
├── server.py             ← Claude Desktop MCP 서버
├── media_processing.py   ← MP3 → MP4 변환
├── youtube_upload.py     ← YouTube 업로드
├── requirements.txt      ← Python 패키지 목록
├── .env                  ← API 키 (직접 생성, Git 제외)
├── suno_actions.json     ← 학습된 UI 좌표 (자동 생성, Git 제외)
├── suno_state.json       ← UI 상태 캐시 (자동 생성, Git 제외)
├── raw_data/             ← 다운로드된 MP3 (자동 생성, Git 제외)
│   ├── 2026-04-01_제목/
│   │   └── song.mp3
│   └── _should_delete/   ← 미선택 곡 임시 보관
├── downloads/            ← 구버전 다운로드 폴더
├── output/               ← MP4 변환 결과물
└── frontend/             ← React 웹 UI
    └── src/
        ├── App.jsx
        ├── api.js
        └── components/
```

---

## 11. 자주 묻는 문제

### Q. 가상환경 활성화를 매번 해야 하나요?

터미널을 새로 열 때마다 아래 두 줄을 실행하세요:

```bash
cd ~/Desktop/SunoAutoPlaylist
source .venv/bin/activate
export $(cat .env | xargs)
```

편하게 하려면 `~/.zshrc` 에 alias를 추가할 수 있습니다:

```bash
echo 'alias suno="cd ~/Desktop/SunoAutoPlaylist && source .venv/bin/activate && export $(cat .env | xargs)"' >> ~/.zshrc
source ~/.zshrc
```

이후 `suno` 명령어 하나로 준비 완료.

---

### Q. pyautogui가 마우스를 움직이지 않아요

macOS 접근성 권한이 없는 경우입니다. [9. macOS 권한 설정](#9-macos-권한-설정) 을 확인하세요.

---

### Q. 스크린샷이 까만 화면으로 나와요

macOS 화면 녹화 권한이 없는 경우입니다. [9. macOS 권한 설정](#9-macos-권한-설정) 을 확인하세요.

---

### Q. 수노 페이지가 열리지 않거나 로그인이 안 돼요

세션이 만료된 경우입니다. 로그인을 다시 저장하세요:

```bash
python suno_login.py
```

---

### Q. UI가 바뀌어서 클릭 위치가 틀려요

자동 재학습을 실행하세요:

```bash
python suno_learn.py --force
```

또는 수동으로 UI 체크만:

```bash
python suno_ui_checker.py --force
```

---

### Q. `suno_actions.json`이 없다는 오류가 나요

`suno_learn.py`를 먼저 실행해야 합니다. [6. 첫 UI 학습](#6-첫-ui-학습-suno_learnpy) 을 참고하세요.

---

### Q. 다운로드 파일이 raw_data/에 없어요

`~/Downloads` 폴더를 직접 확인해보세요. 파일 이동은 `suno_runner.py`가 macOS의 `~/Downloads` 에서 자동으로 가져오는데, 간혹 수노가 다른 폴더에 저장하는 경우가 있습니다.

---

## 전체 실행 순서 요약

```
# ① 처음 한 번만 (환경 세팅)
git clone https://github.com/minsu0192/SunoAutoPlaylist.git
cd SunoAutoPlaylist
git checkout claude/suno-playlist-maker-jixsq
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

# ② 처음 한 번만 (UI 좌표 학습)
# → 먼저 Chrome에서 suno.com/create 열고 Advanced 탭 클릭 후 실행
source .venv/bin/activate
export $(cat .env | xargs)
python suno_learn.py

# ③ 매번 실행
# → Chrome에서 suno.com/create 열고 로그인 확인 후 실행
source .venv/bin/activate
export $(cat .env | xargs)
python suno_runner.py --title "제목" --prompt "가사" --style "스타일" --select longest
```
