#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  수노자동화.app 빌드 스크립트
#  실행: bash build_app.sh
#  결과: dist/수노자동화.app  →  Applications 폴더로 드래그
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -e
cd "$(dirname "$0")"

APP_NAME="수노자동화"
BUNDLE_ID="com.suno.autoplaylist"

echo ""
echo "=================================================="
echo "  🎵 ${APP_NAME}.app 빌드"
echo "=================================================="
echo ""

# ── 가상환경 확인 ────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "❌ .venv 가상환경이 없습니다."
    echo "   먼저 install.sh 를 실행하세요: bash install.sh"
    exit 1
fi
source .venv/bin/activate
echo "[사전 확인] Python: $(python --version)"

# ── 이전 빌드 정리 ───────────────────────────────────
echo ""
echo "[1/4] 이전 빌드 정리..."
rm -rf build dist "${APP_NAME}.spec" 2>/dev/null || true
echo "   ✅ 완료"

# ── entitlements.plist 생성 (화면 캡처 권한) ────────
echo ""
echo "[2/4] 권한 설정 파일 생성..."
cat > entitlements.plist << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.automation.apple-events</key>
    <true/>
    <key>com.apple.security.app-sandbox</key>
    <false/>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
PLIST_EOF
echo "   ✅ 완료"

# ── PyInstaller 빌드 ────────────────────────────────
echo ""
echo "[3/4] .app 빌드 중 (2~5분 소요)..."

# 필요한 Python 파일을 모두 add-data로 포함
DATA_FILES=""
for f in suno_runner.py suno_learn.py suno_ui_checker.py suno_pipeline.py \
         suno_project_manager.py suno_lyrics_gen.py suno_channel_analyzer.py \
         media_processing.py playlist.py youtube_upload.py server.py \
         requirements.txt; do
    if [ -f "$f" ]; then
        DATA_FILES="$DATA_FILES --add-data ${f}:."
    fi
done

# assets 폴더가 있으면 포함
if [ -d "assets" ]; then
    DATA_FILES="$DATA_FILES --add-data assets:assets"
fi

pyinstaller \
  --name "${APP_NAME}" \
  --windowed \
  --onedir \
  --noconfirm \
  --clean \
  $DATA_FILES \
  --hidden-import "rumps" \
  --hidden-import "pyautogui" \
  --hidden-import "anthropic" \
  --hidden-import "PIL" \
  --hidden-import "PIL._tkinter_finder" \
  --hidden-import "anthropic._base_client" \
  --hidden-import "anthropic.types" \
  --hidden-import "tkinter" \
  --hidden-import "tkinter.ttk" \
  --hidden-import "tkinter.filedialog" \
  --hidden-import "tkinter.messagebox" \
  --hidden-import "google.auth" \
  --hidden-import "google.oauth2.credentials" \
  --hidden-import "google_auth_oauthlib.flow" \
  --hidden-import "googleapiclient.discovery" \
  --hidden-import "googleapiclient.http" \
  --hidden-import "pynput" \
  --hidden-import "pynput.keyboard" \
  --hidden-import "playwright" \
  --hidden-import "playwright.async_api" \
  --collect-all "anthropic" \
  --collect-all "rumps" \
  --osx-bundle-identifier "${BUNDLE_ID}" \
  suno_menu_bar.py 2>&1 | grep -v "^$" | grep -v "^\[" | tail -20 || true

echo "   ✅ 빌드 완료"

# ── Info.plist 설정 ──────────────────────────────────
echo ""
echo "[4/4] 앱 설정 적용..."

PLIST="dist/${APP_NAME}.app/Contents/Info.plist"

if [ ! -f "$PLIST" ]; then
    echo "❌ dist/${APP_NAME}.app 빌드 실패. 위 오류를 확인하세요."
    exit 1
fi

# Dock 아이콘 숨김 (메뉴바 전용 앱)
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"

# 권한 설명 문구 (macOS 보안 경고 최소화)
/usr/libexec/PlistBuddy \
  -c "Add :NSAppleEventsUsageDescription string '확인창 표시를 위해 Apple Events를 사용합니다.'" \
  "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy \
  -c "Add :NSScreenCaptureUsageDescription string 'Suno UI 변경 감지를 위해 화면 캡처를 사용합니다.'" \
  "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy \
  -c "Add :NSAccessibilityUsageDescription string '마우스/키보드 자동화를 위해 접근성 권한이 필요합니다.'" \
  "$PLIST" 2>/dev/null || true

# Gatekeeper 격리 해제
xattr -rd com.apple.quarantine "dist/${APP_NAME}.app" 2>/dev/null || true
echo "   ✅ 완료"

# ── 완료 안내 ────────────────────────────────────────
echo ""
echo "=================================================="
echo "✅ 빌드 완료: dist/${APP_NAME}.app"
echo ""
echo "다음 단계:"
echo "  1. dist/${APP_NAME}.app 을 /Applications 폴더로 복사"
echo "     cp -r \"dist/${APP_NAME}.app\" /Applications/"
echo ""
echo "  2. 처음 실행 시 (Gatekeeper 경고 우회):"
echo "     우클릭 → '열기' → '열기' 버튼 클릭"
echo ""
echo "  3. 시스템 설정 → 개인정보 보호 및 보안 에서 허용:"
echo "     • 접근성"
echo "     • 화면 기록 (UI 변경 감지 기능 사용 시)"
echo ""
echo "  4. Launchpad 또는 Spotlight에서 '수노자동화' 검색 후 실행"
echo "     → 메뉴바에 🎵 아이콘이 나타납니다."
echo "=================================================="

# dist 폴더 Finder로 열기
open dist/ 2>/dev/null || true
