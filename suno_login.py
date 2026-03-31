"""
수노 최초 로그인 세션 저장 스크립트
딱 한 번만 실행하면 됩니다.

실행: python3.11 suno_login.py
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

SESSION_FILE = Path(__file__).parent / "suno_session.json"


async def main():
    print("=" * 50)
    print("수노 로그인 세션 저장 도구")
    print("=" * 50)
    print()
    print("브라우저가 열립니다.")
    print("수노에 로그인한 뒤 이 터미널로 돌아와서 Enter를 누르세요.")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox"],
        )
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://suno.com", wait_until="load", timeout=60000)

        print("▶ 브라우저에서 수노 로그인을 완료하세요.")
        print("  (Google 또는 Discord 계정으로 로그인)")
        print()
        input("로그인 완료 후 여기서 Enter ▶ ")

        # 로그인 확인
        try:
            await page.wait_for_selector(
                "button:has-text('Create'), a[href='/create']",
                timeout=5000,
            )
            state = await context.storage_state()
            SESSION_FILE.write_text(json.dumps(state))
            print()
            print("✅ 로그인 세션 저장 완료!")
            print(f"   저장 위치: {SESSION_FILE}")
            print()
            print("이제 api.py를 실행하면 자동으로 로그인된 상태로 동작합니다.")
        except Exception:
            print()
            print("❌ 로그인이 확인되지 않았습니다. 다시 시도해주세요.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
