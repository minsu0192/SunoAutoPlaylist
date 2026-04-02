#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  수노자동화 설치 스크립트
#  처음 한 번만 실행하세요.
#  실행: bash install.sh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -e
cd "$(dirname "$0")"

echo ""
echo "=================================================="
echo "  🎵 수노자동화 설치"
echo "=================================================="
echo ""

# ── 1. Python 버전 확인 ──────────────────────────────
echo "[1/6] Python 확인..."
if command -v python3.11 &>/dev/null; then
    PYTHON="python3.11"
elif command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_VER" -ge 10 ]; then
        PYTHON="python3"
    else
        echo "❌ Python 3.10 이상이 필요합니다."
        echo "   https://www.python.org/downloads/ 에서 설치하세요."
        exit 1
    fi
else
    echo "❌ Python이 설치되지 않았습니다."
    echo "   https://www.python.org/downloads/ 에서 설치하세요."
    exit 1
fi
echo "   ✅ $($PYTHON --version)"

# ── 2. 가상환경 ─────────────────────────────────────
echo "[2/6] 가상환경 생성..."
if [ -d ".venv" ]; then
    echo "   ✅ 기존 .venv 사용"
else
    $PYTHON -m venv .venv
    echo "   ✅ .venv 생성 완료"
fi
source .venv/bin/activate

# ── 3. 패키지 설치 ──────────────────────────────────
echo "[3/6] 패키지 설치 중 (1~3분 소요)..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "   ✅ 패키지 설치 완료"

# ── 4. Playwright 브라우저 ─────────────────────────
echo "[4/6] Playwright Chromium 설치..."
python -m playwright install chromium 2>&1 | tail -3
echo "   ✅ 브라우저 준비 완료"

# ── 5. 실행 권한 ──────────────────────────────────
echo "[5/6] 실행 파일 권한 설정..."
chmod +x "실행.command"
chmod +x "build_app.sh"
# Gatekeeper 격리 해제 (더블클릭 시 "개발자 확인 불가" 오류 방지)
xattr -d com.apple.quarantine "실행.command" 2>/dev/null || true
echo "   ✅ 권한 설정 완료"

# ── 6. 첫 실행 안내 ───────────────────────────────
echo "[6/6] 설치 완료!"
echo ""
echo "=================================================="
echo "✅ 설치 완료!"
echo ""
echo "사용 방법:"
echo "  ① '실행.command' 파일을 더블클릭하면 앱이 시작됩니다."
echo "  ② 메뉴바 상단에 🎵 아이콘이 나타납니다."
echo "  ③ 🎵 클릭 → ⚙️ 설정에서 API 키를 입력하세요."
echo ""
echo ".app 번들로 빌드하려면:"
echo "  bash build_app.sh"
echo "=================================================="
echo ""

# 설치 완료 후 앱 바로 실행 여부 묻기
read -p "지금 바로 앱을 실행하시겠습니까? (y/n): " ANSWER
if [[ "$ANSWER" == "y" || "$ANSWER" == "Y" ]]; then
    open "실행.command"
fi
