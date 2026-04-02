# 수노 자동화 — macOS 메뉴바 앱

이미지 파일 드래그 → 가사/스타일 자동 생성 → Suno 자동 조작 → MP4 생성 → YouTube 자동 업로드

---

## 전체 워크플로

```
~/SunoProjects/input/집에가고싶다.jpg
        ↓  (파일명 = 키워드)
Claude API (1회/곡)
  → 가사 + Suno 스타일 + 곡 제목
  → YouTube 제목 + 설명 (참고 채널 스타일 반영)
        ↓
pyautogui → Suno.com 자동 조작
  → 가사/스타일/제목 입력 → Create 클릭
  → MP3 자동 다운로드
        ↓
FFmpeg → 커버이미지 + MP3 → MP4
        ↓
YouTube Data API → 자동 업로드
```

---

## 폴더 구조

```
~/SunoProjects/
  input/           ← 이미지를 여기에 드래그 (파일명 = 곡 키워드)
  projects/
    2026-04-01_집에가고싶다/
      cover.jpg
      content.json     ← 가사/스타일/제목 (Claude 생성)
      output.mp3
      output.mp4
      result.json      ← YouTube URL 등
```

---

## 설치 (최초 1회 — 터미널)

```bash
git clone https://github.com/minsu0192/SunoAutoPlaylist.git
cd SunoAutoPlaylist
git checkout claude/suno-playlist-maker-jixsq

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 최초 설정

```bash
python suno_menu_bar.py   # 메뉴바 앱 실행
```

메뉴바 🎵 아이콘 → **⚙️ 설정** 클릭

### 기본 설정 탭
| 항목 | 내용 |
|------|------|
| Anthropic API 키 | [console.anthropic.com](https://console.anthropic.com) 에서 발급 |
| 프로젝트 폴더 | 원하는 폴더 선택 (기본: ~/SunoProjects) |
| 음악 스타일 | 프리셋 선택 or 직접 입력 |
| 보컬 타입 | 여성 / 남성 / 없음 |
| 곡 수 | 1~20곡 (Suno 크레딧 주의) |
| 곡 선택 방식 | 가장 긴 곡 / 랜덤 / 수동 |

### YouTube 탭
1. **client_secrets.json** 선택 (Google Cloud Console에서 다운로드)
2. **YouTube 계정 인증** 버튼 → 브라우저 열림 → 로그인 → 허용
3. **채널 분석 URL** 입력 → **채널 분석** 버튼 **(1회만 실행)**
   → 이후 업로드 제목/설명이 해당 채널 스타일로 자동 생성됨

### 고급 설정 탭
| 항목 | 내용 |
|------|------|
| 예약 실행 | 요일 체크 + 시간 선택 (예: 월~금 새벽 2시) |
| 녹화 학습 | Suno UI 좌표 학습 (처음 한 번 필수) |

---

## UI 좌표 학습 (처음 한 번 필수)

설정 → 고급 설정 → **🎬 녹화 학습** 클릭

```
① Chrome에서 suno.com/create → Advanced 탭 열기
② 자연스럽게 워크플로를 진행하면서
   각 요소 위에 마우스가 있을 때 해당 숫자 키를 누르세요:

   [1] Advanced 탭
   [2] Lyrics 입력창
   [3] Styles 입력창
   [4] Song Title 입력창
   [5] Create 버튼
   [6] 생성된 곡의 ... 버튼  (Create 후 곡이 생성되면)
   [7] 다운로드 버튼          (... 클릭 후 메뉴가 열리면)
   [0] 종료 및 저장
```

---

## 사용법

### 방법 1: 즉시 실행
1. `~/SunoProjects/input/` 폴더에 이미지 드래그
   - 파일명이 곡 키워드: `집에가고싶다.jpg`, `sunset_calm.png`
2. 메뉴바 🎵 → **▶ 지금 실행**

### 방법 2: 예약 실행
설정 → 고급 설정 → 예약 활성화 + 요일/시간 설정
→ 지정한 시간에 자동 실행

### 메뉴 구성
| 메뉴 항목 | 기능 |
|----------|------|
| ▶ 지금 실행 (N개 대기) | 큐 첫 번째 프로젝트 즉시 실행 |
| 📂 입력 폴더 열기 | ~/SunoProjects/input/ 열기 |
| 📁 결과물 폴더 열기 | 완성된 MP4 폴더 열기 |
| 📋 로그 보기 | 최근 실행 로그 확인 |
| ⚙️ 설정 | 설정 창 열기 |

---

## Claude API 사용 시점 (1곡당 최대 1회)

| 시점 | 용도 | 모델 |
|------|------|------|
| 곡 생성 시 | 가사 + 스타일 + YouTube 제목/설명 한 번에 생성 | Claude Haiku (저렴) |
| 채널 분석 시 **(딱 1회)** | YouTube 채널 스타일 분석 후 템플릿 저장 | Claude Haiku |

---

## YouTube 연동

### Google Cloud Console 설정
1. [console.cloud.google.com](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성
3. API 및 서비스 → YouTube Data API v3 활성화
4. 사용자 인증 정보 → OAuth 2.0 클라이언트 ID 생성
   - 애플리케이션 유형: **데스크톱 앱**
5. JSON 다운로드 → 파일 경로를 설정에서 지정

### 인증 흐름
- 설정 → YouTube 탭 → **YouTube 계정 인증** 버튼
- 브라우저 열림 → 구글 계정 선택 → 허용
- `token.json` 저장됨 → 이후 자동 로그인 유지

---

## .app 빌드 (완전 터미널 없이 사용)

```bash
source .venv/bin/activate
pyinstaller --onefile --windowed --name SunoAuto suno_menu_bar.py
# dist/SunoAuto.app → Applications 폴더로 이동 → Dock 등록
```

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| pyautogui 접근성 오류 | 시스템 설정 → 개인정보 → 손쉬운 사용 → Terminal 허용 |
| 스크린샷 검은 화면 | 시스템 설정 → 화면 녹화 → Terminal 허용 |
| API 401 오류 | 설정에서 Anthropic API 키 재입력 |
| YouTube 인증 실패 | client_secrets.json 경로 확인 |
| yt-dlp 없음 | `pip install yt-dlp` |
| pynput 없음 | `pip install pynput` |
