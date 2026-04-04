# UI 학습 (learn.py)

좌표 저장 위치: `~/.suno_actions.json`

## 학습 단계

### 1단계: Advanced 모드

Chrome에서 suno.com/create를 열고 각 요소 위에 마우스를 올린 뒤 기록.

| 키 | 요소 |
|----|------|
| `advanced_tab` | Advanced 탭 |
| `lyrics_input` | 가사 입력칸 |
| `style_input` | 스타일 입력칸 |
| `title_input` | 제목 입력칸 |
| `create_btn` | Create 버튼 |

### 2단계: 다운로드

이미 생성된 곡이 페이지에 있으면 그걸로 학습 (새로 만들 필요 없음).

| 키 | 요소 | 방식 |
|----|------|------|
| `song_dot_btn` | 첫 번째 곡의 ... 버튼 | 일반 (올리고 기록) |
| `song_dot_btn_2` | 두 번째 곡의 ... 버튼 | 일반 |
| `download_item` | Download 메뉴 항목 | 타이머 (5초) — ... 클릭 후 Download 위에 hover |
| `mp3_btn` | MP3 버튼 | 타이머 (5초) — ... → Download hover → MP3 위에 hover |

### 3단계: Instrumental (선택)

Simple 탭을 클릭한 상태에서 학습. 건너뛰기 가능.

| 키 | 요소 |
|----|------|
| `simple_tab` | Simple 탭 |
| `song_desc_input` | Song Description 입력칸 |
| `instrumental_toggle` | Instrumental 버튼 |
| `simple_create_btn` | Create 버튼 |

## 타이머 방식

Download/MP3 학습은 메뉴를 열어야 보이므로:
1. "시작" 클릭 → 대화창 닫힘
2. 5초 카운트다운 (알림으로 표시)
3. 5초 안에 메뉴를 열고 해당 위치에 마우스를 올려놓기
4. 자동으로 좌표 기록
