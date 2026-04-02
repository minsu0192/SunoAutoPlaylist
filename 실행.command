#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  수노자동화 — 더블클릭 실행 파일
#  Finder에서 이 파일을 더블클릭하면 앱이 시작됩니다.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 스크립트 위치로 이동
cd "$(dirname "$0")"

# 터미널 제목 설정
echo -e "\033]0;수노자동화 실행 중\007"

echo ""
echo "=================================================="
echo "  🎵 수노자동화 시작 중..."
echo "=================================================="
echo ""

# Python 실행환경 탐색 (우선순위: .venv → python3.11 → python3)
if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3.11 &>/dev/null; then
    PYTHON="python3.11"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    osascript -e 'display alert "Python을 찾을 수 없습니다." message "https://www.python.org 에서 Python 3.11을 설치하세요." as critical'
    exit 1
fi

echo "Python: $($PYTHON --version)"
echo ""

# 필수 패키지 확인
$PYTHON -c "import rumps" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚙️  첫 실행: 필수 패키지 설치 중 (1~3분 소요)..."
    echo ""
    $PYTHON -m pip install -r requirements.txt -q
    if [ $? -ne 0 ]; then
        osascript -e 'display alert "패키지 설치 실패" message "터미널에서 오류를 확인하세요.\npip install -r requirements.txt" as critical'
        exit 1
    fi
    echo "✅ 설치 완료"
    echo ""
fi

# Playwright 브라우저 확인
$PYTHON -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__().chromium" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚙️  Playwright 브라우저 설치 중..."
    $PYTHON -m playwright install chromium 2>/dev/null || true
fi

echo "🎵 수노자동화 메뉴바 앱 실행..."
echo "   (메뉴바 상단에 🎵 아이콘이 나타납니다)"
echo "   (이 터미널 창은 닫아도 됩니다)"
echo ""

# 메뉴바 앱 실행 (백그라운드)
$PYTHON suno_menu_bar.py &
APP_PID=$!

# 3초 후 정상 실행 확인
sleep 3
if ! kill -0 $APP_PID 2>/dev/null; then
    echo "❌ 앱 실행에 실패했습니다. 아래 로그를 확인하세요:"
    cat ~/.suno_auto.log 2>/dev/null | tail -20
    echo ""
    read -p "아무 키나 누르면 창이 닫힙니다..."
    exit 1
fi

echo "✅ 실행 중 (PID: $APP_PID)"
echo "   메뉴바의 🎵 아이콘을 클릭하세요."
echo ""

# 터미널 창 자동 닫기 (3초 후)
sleep 3
osascript -e 'tell application "Terminal" to close (every window whose name contains "수노자동화 실행 중")' 2>/dev/null || true
