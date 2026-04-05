#!/bin/bash
# 수노자동화.app 빌드 스크립트
# 실행: bash build_app.sh
set -e

cd "$(dirname "$0")"

echo "=================================================="
echo "  수노자동화.app 빌드 시작"
echo "=================================================="

# 가상환경 활성화
if [ ! -d ".venv" ]; then
  echo "❌ .venv 가상환경이 없습니다. 먼저 설치를 완료하세요."
  echo "   python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
source .venv/bin/activate

echo ""
echo "[1/3] rumps, pyinstaller 설치 중..."
pip install -q "rumps>=0.4.0" "pyinstaller>=6.0.0"

echo ""
echo "[2/3] .app 빌드 중 (1~2분 소요)..."

pyinstaller \
  --name "수노자동화" \
  --windowed \
  --onedir \
  --noconfirm \
  --add-data "suno_runner.py:." \
  --add-data "suno_learn.py:." \
  --add-data "suno_ui_checker.py:." \
  --add-data "media_processing.py:." \
  --add-data "playlist.py:." \
  --add-data "requirements.txt:." \
  --hidden-import "rumps" \
  --hidden-import "pyautogui" \
  --hidden-import "anthropic" \
  --hidden-import "PIL" \
  --hidden-import "fastapi" \
  --hidden-import "uvicorn" \
  --osx-bundle-identifier "com.suno.autoplaylist" \
  suno_menu_bar.py

echo ""
echo "[3/3] Info.plist 설정 (Dock 아이콘 숨김)..."

PLIST="dist/수노자동화.app/Contents/Info.plist"

# LSUIElement = true → 독(Dock) 아이콘 없이 메뉴바만 표시
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"

# NSAppleEventsUsageDescription (osascript 권한 설명)
/usr/libexec/PlistBuddy \
  -c "Add :NSAppleEventsUsageDescription string '입력창 표시를 위해 Apple Events를 사용합니다.'" \
  "$PLIST" 2>/dev/null || true

echo ""
echo "=================================================="
echo "✅ 빌드 완료: dist/수노자동화.app"
echo ""
echo "다음 단계:"
echo "  1. dist/수노자동화.app 을 Applications 폴더로 드래그"
echo "  2. 처음 실행 시: 우클릭 → 열기 → 열기 (보안 경고 우회)"
echo "  3. 시스템 환경설정 → 개인정보 보호 → 접근성에서 '수노자동화' 허용"
echo "  4. 이후 Launchpad에서 '수노자동화' 실행 → 메뉴바에 🎵 아이콘 표시"
echo "=================================================="
