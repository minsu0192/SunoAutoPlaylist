"""
수노(Suno) 브라우저 자동화 모듈
Playwright를 사용해 수노 웹사이트를 자동 조작합니다.

주의: 수노 이용약관상 자동화는 금지되어 있습니다.
      계정 정지 위험이 있으므로 개인 용도로만 사용하세요.
"""

import asyncio
import json
import re
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("[경고] playwright-stealth 미설치 → 봇 감지 우회 비활성화")


SUNO_URL     = "https://suno.com"
SESSION_FILE = Path(__file__).parent / "suno_session.json"


class SunoAutomation:
    def __init__(self, download_dir: Path):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)

    async def generate(self, title: str, prompt: str, style: str = "", count: int = 2) -> dict:
        async with async_playwright() as p:
            context = await self._create_context(p)
            page = await context.new_page()

            if STEALTH_AVAILABLE:
                await stealth_async(page)

            try:
                result = await self._run_generation(page, title, prompt, style, count)
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}
            finally:
                await context.close()

    async def _create_context(self, p):
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        if SESSION_FILE.exists():
            print("[브라우저] 저장된 세션으로 시작")
            state = json.loads(SESSION_FILE.read_text())
            return await browser.new_context(storage_state=state)
        print("[브라우저] 세션 없음 → 새 브라우저로 시작 (로그인 필요)")
        return await browser.new_context()

    async def _run_generation(self, page: Page, title: str, prompt: str, style: str, count: int) -> dict:

        await page.goto(SUNO_URL, wait_until="load", timeout=60000)
        await asyncio.sleep(2)

        if not await self._is_logged_in(page):
            return {"success": False, "error": "수노 로그인이 필요합니다. 터미널에서 python3.11 suno_login.py 를 먼저 실행해 로그인해주세요."}

        await page.click("a[href='/create'], button:has-text('Create')")
        await asyncio.sleep(1)

        custom_toggle = page.locator("button:has-text('Custom'), label:has-text('Custom')")
        if await custom_toggle.count() > 0:
            await custom_toggle.first.click()
            await asyncio.sleep(0.5)

        prompt_area = page.locator("textarea[placeholder*='lyric'], textarea[placeholder*='prompt'], textarea").first
        await prompt_area.fill(prompt)

        if style:
            style_input = page.locator("input[placeholder*='style'], input[placeholder*='Style']").first
            if await style_input.count() > 0:
                await style_input.fill(style)

        title_input = page.locator("input[placeholder*='title'], input[placeholder*='Title']").first
        if await title_input.count() > 0:
            await title_input.fill(title)

        await page.click("button:has-text('Create'), button[type='submit']:has-text('Generate')")
        print(f"[수노] '{title}' 생성 시작... (2~3분 소요)")

        song_urls = await self._wait_for_songs(page, count, timeout=300)

        downloaded = []
        for i, url in enumerate(song_urls):
            filename = f"{self._safe_filename(title)}_{i+1}.mp3"
            filepath = self.download_dir / filename
            await self._download_mp3(page, url, filepath)
            downloaded.append(filename)
            print(f"[수노] 다운로드 완료: {filename}")

        return {
            "success": True,
            "title": title,
            "downloaded_files": downloaded,
            "count": len(downloaded),
        }

    async def _wait_for_songs(self, page: Page, count: int, timeout: int) -> list[str]:
        start = time.time()
        while time.time() - start < timeout:
            urls = await page.evaluate("""
                () => Array.from(document.querySelectorAll('audio[src]'))
                          .map(a => a.src)
                          .filter(s => s.includes('.mp3') || s.includes('cdn'))
            """)
            if len(urls) >= count:
                return urls[:count]
            await asyncio.sleep(5)
            print(f"[수노] 생성 중... ({int(time.time()-start)}초 경과)")
        raise TimeoutError(f"{timeout}초 안에 곡 생성이 완료되지 않았습니다.")

    async def _download_mp3(self, page: Page, audio_url: str, filepath: Path):
        response = await page.context.request.get(audio_url)
        filepath.write_bytes(await response.body())

    async def _is_logged_in(self, page: Page) -> bool:
        try:
            await page.wait_for_selector(
                "button:has-text('Create'), a[href='/create']",
                timeout=5000,
            )
            return True
        except Exception:
            return False

    async def _save_session(self, context: BrowserContext):
        state = await context.storage_state()
        SESSION_FILE.write_text(json.dumps(state))
        print("[세션] 로그인 상태 저장 완료.")

    @staticmethod
    def _safe_filename(name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()
