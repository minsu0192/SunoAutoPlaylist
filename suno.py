"""
수노(Suno) 브라우저 자동화 모듈 — Playwright 기반
CSS 셀렉터로 UI 요소를 찾아 자동 조작합니다.
pyautogui 좌표 방식보다 안정적이며 해상도에 독립적입니다.

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

SUNO_URL = "https://suno.com"
CREATE_URL = f"{SUNO_URL}/create"
SESSION_FILE = Path(__file__).parent / "suno_session.json"

# ---------------------------------------------------------------------------
# 다중 셀렉터 — Suno UI 변경에 대응하기 위해 여러 후보를 시도
# ---------------------------------------------------------------------------
SELECTORS = {
    "create_link": [
        "a[href='/create']",
        "button:has-text('Create')",
        "[data-testid='create-button']",
    ],
    "advanced_tab": [
        "button:has-text('Advanced')",
        "button:has-text('Custom')",
        "label:has-text('Custom')",
        "[data-testid='custom-toggle']",
    ],
    "lyrics_textarea": [
        "textarea[placeholder*='lyric']",
        "textarea[placeholder*='Lyric']",
        "textarea[placeholder*='Write your own']",
        "textarea[placeholder*='prompt']",
        "textarea",
    ],
    "style_input": [
        "input[placeholder*='style']",
        "input[placeholder*='Style']",
        "input[placeholder*='genre']",
        "input[placeholder*='Genre']",
        "[data-testid='style-input']",
    ],
    "title_input": [
        "input[placeholder*='title']",
        "input[placeholder*='Title']",
        "input[placeholder*='Song name']",
        "[data-testid='title-input']",
    ],
    "create_button": [
        "button:has-text('Create')",
        "button[type='submit']:has-text('Create')",
        "button[type='submit']:has-text('Generate')",
        "[data-testid='create-submit']",
    ],
    "song_menu_btn": [
        "button[aria-label='More options']",
        "button[aria-label='Song options']",
        "button:has-text('⋮')",
        "button:has-text('...')",
        "[data-testid='song-menu']",
    ],
    "download_btn": [
        "button:has-text('Download')",
        "a:has-text('Download')",
        "[data-testid='download-button']",
        "button:has-text('MP3')",
    ],
}


async def _find_element(page: Page, key: str, timeout: int = 5000):
    """다중 셀렉터 중 첫 번째로 찾이는 요소를 반환."""
    selectors = SELECTORS.get(key, [key])
    for selector in selectors:
        try:
            el = page.locator(selector).first
            await el.wait_for(state="visible", timeout=timeout)
            return el
        except Exception:
            continue
    raise Exception(f"[Suno] '{key}' 요소를 찾을 수 없습니다. 시도한 셀렉터: {selectors}")


async def _find_element_safe(page: Page, key: str, timeout: int = 3000):
    """요소를 찾되, 없으면 None 반환 (에러 없음)."""
    try:
        return await _find_element(page, key, timeout)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 메인 클래스
# ---------------------------------------------------------------------------
class SunoAutomation:
    """Playwright 기반 Suno 자동화. CSS 셀렉터로 UI 조작."""

    def __init__(self, download_dir: Path, headless: bool = False,
                 max_retries: int = 2):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.max_retries = max_retries

    async def generate(self, title: str, prompt: str, style: str = "",
                       count: int = 2, select: str = "longest") -> dict:
        """
        Suno에서 곡 생성 → MP3 다운로드.
        실패 시 max_retries까지 재시도.

        Returns:
            {
                "success": bool,
                "title": str,
                "downloaded_files": [Path, ...],
                "count": int,
                "error": str (실패 시),
            }
        """
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            print(f"\n[Suno] 시도 {attempt}/{self.max_retries}")
            try:
                result = await self._attempt_generate(
                    title, prompt, style, count, select
                )
                if result.get("success"):
                    return result
                last_error = result.get("error", "알 수 없는 오류")
                print(f"[Suno] 시도 {attempt} 실패: {last_error}")
            except Exception as e:
                last_error = str(e)
                print(f"[Suno] 시도 {attempt} 예외: {last_error}")

            if attempt < self.max_retries:
                wait = attempt * 5
                print(f"[Suno] {wait}초 후 재시도...")
                await asyncio.sleep(wait)

        return {"success": False, "error": f"최대 재시도 초과: {last_error}"}

    async def _attempt_generate(self, title, prompt, style, count, select) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = await self._load_session(browser)

            # 다운로드 경로 설정
            tmp_dl = self.download_dir / "_tmp_downloads"
            tmp_dl.mkdir(exist_ok=True)

            page = await context.new_page()

            if STEALTH_AVAILABLE:
                await stealth_async(page)

            try:
                result = await self._run_generation(
                    page, title, prompt, style, count, select, tmp_dl
                )
                await self._save_session(context)
                return result
            finally:
                await browser.close()
                # 임시 폴더 정리
                if tmp_dl.exists() and not any(tmp_dl.iterdir()):
                    tmp_dl.rmdir()

    async def _run_generation(self, page: Page, title: str, prompt: str,
                              style: str, count: int, select: str,
                              tmp_dl: Path) -> dict:
        # ── 1. 페이지 이동 ──
        print("[1/8] suno.com/create 이동...")
        await page.goto(CREATE_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # ── 2. 로그인 확인 ──
        print("[2/8] 로그인 상태 확인...")
        if not await self._is_logged_in(page):
            print("  ⚠️ 로그인 필요 — 브라우저에서 로그인 후 Enter")
            input("  로그인 완료 후 Enter ▶ ")
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(2)

        # ── 3. Advanced/Custom 탭 ──
        print("[3/8] Advanced 탭 클릭...")
        advanced = await _find_element_safe(page, "advanced_tab", timeout=5000)
        if advanced:
            await advanced.click()
            await asyncio.sleep(1)
        else:
            print("  ℹ️ Advanced 탭 없음 — 이미 커스텀 모드이거나 UI 변경")

        # ── 4. 가사 입력 ──
        print("[4/8] 가사 입력...")
        lyrics_el = await _find_element(page, "lyrics_textarea")
        await lyrics_el.click()
        await lyrics_el.fill(prompt)
        await asyncio.sleep(0.5)

        # ── 5. 스타일 입력 ──
        if style:
            print("[5/8] 스타일 입력...")
            style_el = await _find_element_safe(page, "style_input")
            if style_el:
                await style_el.click()
                await style_el.fill(style)
                await asyncio.sleep(0.5)
            else:
                print("  ⚠️ 스타일 입력란 없음 — 건너뜀")
        else:
            print("[5/8] 스타일 건너뜀")

        # ── 6. 제목 입력 ──
        print("[6/8] 제목 입력...")
        title_el = await _find_element_safe(page, "title_input")
        if title_el:
            await title_el.click()
            await title_el.fill(title)
            await asyncio.sleep(0.5)
        else:
            print("  ⚠️ 제목 입력란 없음 — 건너뜀")

        # ── 7. Create 클릭 + 생성 대기 ──
        print("[7/8] Create 클릭...")
        create_btn = await _find_element(page, "create_button")
        await create_btn.click()
        print(f"  '{title}' 생성 시작 (2~3분 소요)...")

        song_urls = await self._wait_for_songs(page, count, timeout=300)
        print(f"  ✅ {len(song_urls)}곡 생성 완료")

        # ── 8. 다운로드 ──
        print("[8/8] MP3 다운로드...")
        downloaded = []
        for i, url in enumerate(song_urls):
            safe_name = self._safe_filename(title)
            filename = f"{safe_name}_{i+1}.mp3"
            filepath = self.download_dir / filename
            await self._download_mp3(page, url, filepath)
            downloaded.append(filepath)
            print(f"  다운로드 완료: {filename}")

        # 곡 선택
        final = self._select_songs(downloaded, select)

        return {
            "success": True,
            "title": title,
            "downloaded_files": final,
            "count": len(final),
        }

    # ── 곡 생성 대기 ──
    async def _wait_for_songs(self, page: Page, count: int,
                              timeout: int = 300) -> list[str]:
        """audio 태그의 src에서 MP3 URL을 감지할 때까지 대기."""
        start = time.time()
        last_count = 0
        while time.time() - start < timeout:
            urls = await page.evaluate("""
                () => {
                    const audios = document.querySelectorAll('audio[src]');
                    return Array.from(audios)
                        .map(a => a.src)
                        .filter(s => s.includes('.mp3') || s.includes('cdn'));
                }
            """)
            if len(urls) >= count:
                return urls[:count]

            elapsed = int(time.time() - start)
            if len(urls) != last_count:
                print(f"  {len(urls)}곡 감지... ({elapsed}초)")
                last_count = len(urls)
            elif elapsed % 30 == 0 and elapsed > 0:
                print(f"  생성 중... ({elapsed}초)")

            await asyncio.sleep(5)

        raise TimeoutError(f"{timeout}초 안에 곡 생성이 완료되지 않았습니다.")

    # ── MP3 다운로드 ──
    async def _download_mp3(self, page: Page, audio_url: str, filepath: Path):
        response = await page.context.request.get(audio_url)
        filepath.write_bytes(await response.body())

    # ── 곡 선택 ──
    def _select_songs(self, files: list[Path], mode: str) -> list[Path]:
        if len(files) <= 1 or mode == "manual":
            return files

        if mode == "random":
            import random
            kept = random.choice(files)
            for f in files:
                if f != kept:
                    f.unlink(missing_ok=True)
            print(f"  🎲 랜덤 선택: {kept.name}")
            return [kept]

        if mode == "longest":
            sizes = {f: f.stat().st_size for f in files}
            kept = max(sizes, key=sizes.get)
            for f in files:
                if f != kept:
                    f.unlink(missing_ok=True)
            print(f"  📏 긴 곡 선택: {kept.name}")
            return [kept]

        return files

    # ── 로그인 확인 ──
    async def _is_logged_in(self, page: Page) -> bool:
        try:
            await page.wait_for_selector(
                "button:has-text('Create'), a[href='/create'], [data-testid='create-button']",
                timeout=8000,
            )
            return True
        except Exception:
            return False

    # ── 세션 저장/로드 ──
    async def _load_session(self, browser):
        if SESSION_FILE.exists():
            try:
                state = json.loads(SESSION_FILE.read_text())
                return await browser.new_context(storage_state=state)
            except Exception:
                print("[세션] 저장된 세션 손상 — 새 세션 시작")
        return await browser.new_context()

    async def _save_session(self, context: BrowserContext):
        try:
            state = await context.storage_state()
            SESSION_FILE.write_text(json.dumps(state))
        except Exception as e:
            print(f"[세션] 저장 실패: {e}")

    @staticmethod
    def _safe_filename(name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()[:60]
