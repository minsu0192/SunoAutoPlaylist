# 브라우저 자동화 (suno_bot.py)

## 클릭 메커니즘

macOS Quartz CoreGraphics 네이티브 이벤트 사용 (pyautogui.click() 대신).

### _click(x, y)
1. `CGEventMouseMoved` → 마우스 이동 (웹 요소 hover 인식)
2. 0.15초 대기
3. `CGEventLeftMouseDown` → 마우스 누르기
4. 0.05초 대기
5. `CGEventLeftMouseUp` → 마우스 떼기
6. delay초 대기

### _hover(x, y)
`CGEventMouseMoved`만 발생 (클릭 안 함). Download 드롭다운 메뉴에 사용.

### _clear_and_type(x, y, text)
클릭 → Cmd+A → Delete → 클립보드 복사 → Cmd+V 붙여넣기

## 브라우저 관리

`_ensure_browser()`:
- 첫 세션: Chrome 다운로드 경로를 `~/SunoOutput/downloads/`로 변경 → Chrome 재시작 → suno.com 열기
- 이후 세션: Chrome 포커스만 가져오기 (새 탭 안 열림)

다운로드 경로: `~/SunoOutput/downloads/` (macOS TCC 권한 팝업 없음)

## 보컬 세션 흐름

1. 브라우저 열기 (첫 세션만)
2. Advanced 탭 클릭
3. 가사 입력
4. 스타일 입력
5. 제목 입력
6. Create 클릭
7. 90초 대기
8. 다운로드 (2곡)
9. vocal_pick에 따라 선택

## Instrumental 세션 흐름

1. 브라우저 열기 (첫 세션만)
2. Simple 탭 클릭
3. Instrumental 토글 클릭
4. Song Description 입력 (Claude 생성)
5. Create 클릭
6. 90초 대기
7. 다운로드 (2곡 모두 사용)

## 다운로드 흐름

각 곡:
1. `...` 버튼 **클릭** (song_dot_btn / song_dot_btn_2)
2. Download 메뉴 **hover** (마우스 올리기만, 클릭 X)
3. MP3 버튼 **클릭**
