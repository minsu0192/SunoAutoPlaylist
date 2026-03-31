"""
크롬에 저장된 수노 쿠키를 추출해서 세션 파일로 저장합니다.
크롬에서 수노 로그인이 되어 있어야 합니다.

실행: python3.11 suno_export_cookies.py
"""

import json
from pathlib import Path

SESSION_FILE = Path(__file__).parent / "suno_session.json"

try:
    import browser_cookie3
except ImportError:
    print("❌ browser-cookie3 미설치")
    print("   pip3.11 install browser-cookie3  실행 후 다시 시도하세요.")
    exit(1)


def main():
    print("크롬에서 수노 쿠키 추출 중...")
    print("(키체인 접근 허용 팝업이 뜨면 허용해주세요)")
    print()

    try:
        cookies = browser_cookie3.chrome(domain_name=".suno.com")
        cookie_list = []
        for c in cookies:
            cookie_list.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "expires": c.expires,
                "httpOnly": False,
                "secure": c.secure,
                "sameSite": "Lax",
            })

        if not cookie_list:
            print("❌ 수노 쿠키를 찾지 못했습니다.")
            print("   크롬에서 suno.com에 로그인 후 다시 시도하세요.")
            return

        session = {"cookies": cookie_list, "origins": []}
        SESSION_FILE.write_text(json.dumps(session, indent=2))

        print(f"✅ 쿠키 {len(cookie_list)}개 추출 완료!")
        print(f"   저장 위치: {SESSION_FILE}")
        print()
        print("이제 python3.11 api.py 를 실행하면 자동으로 로그인된 상태로 동작합니다.")

    except Exception as e:
        print(f"❌ 오류: {e}")
        print()
        print("크롬이 완전히 닫혀 있어야 합니다. (⌘Q로 종료 후 재시도)")


if __name__ == "__main__":
    main()
