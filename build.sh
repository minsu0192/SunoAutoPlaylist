#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=================================================="
echo "  수노자동화.app 빌드"
echo "=================================================="

if [ ! -d ".venv" ]; then
  echo "[0/3] 가상환경 생성..."
  python3.11 -m venv .venv
fi
source .venv/bin/activate

echo "[1/3] 패키지 설치..."
pip install -q -r requirements.txt pyinstaller

echo "[2/3] .app 빌드 중..."
pyinstaller \
  --name "수노자동화" \
  --windowed \
  --onedir \
  --noconfirm \
  --add-data "config.py:." \
  --add-data "queue_manager.py:." \
  --add-data "pipeline.py:." \
  --add-data "suno_bot.py:." \
  --add-data "lyrics_gen.py:." \
  --add-data "media_proc.py:." \
  --add-data "yt_upload.py:." \
  --add-data "learn.py:." \
  --hidden-import "tkinterdnd2" \
  --collect-all "tkinterdnd2" \
  --collect-all "customtkinter" \
  --hidden-import "pyautogui" \
  --hidden-import "anthropic" \
  --hidden-import "Quartz" \
  --hidden-import "googleapiclient" \
  --hidden-import "google_auth_oauthlib" \
  --icon "icon.icns" \
  --osx-bundle-identifier "com.suno.auto" \
  app.py

echo "[3/3] Info.plist 설정..."
PLIST="dist/수노자동화.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string 'UI 자동화에 사용합니다.'" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :NSDownloadsFolderUsageDescription string '생성된 MP3 파일을 가져옵니다.'" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :NSAccessibilityUsageDescription string '마우스/키보드 자동 조작에 사용합니다.'" "$PLIST" 2>/dev/null || true

xattr -cr dist/수노자동화.app 2>/dev/null || true
codesign -s - --force --deep dist/수노자동화.app 2>/dev/null || true

# Applications에 복사 (바탕화면은 iCloud 중복 생김)
rm -rf /Applications/수노자동화.app 2>/dev/null || true
cp -R dist/수노자동화.app /Applications/수노자동화.app

echo ""
echo "=================================================="
echo "✅ 빌드 완료: dist/수노자동화.app"
echo "  → /Applications/수노자동화.app 에 설치됨"
echo "=================================================="
