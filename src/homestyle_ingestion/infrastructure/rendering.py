from playwright.async_api import Browser, Error, Page, Playwright, TimeoutError, async_playwright

from homestyle_ingestion.domain.rendering import RenderPageError


async def _expand_collapsed_sections(page: Page, pause_ms: int = 800) -> int:
    selectors = [
        "text=상품정보 더보기",
        "text=더보기",
        "button:has-text('더보기')",
        "a:has-text('더보기')",
        "[class*='more']:has-text('더보기')",
    ]
    clicked = 0
    for selector in selectors:
        elements = await page.query_selector_all(selector)
        for element in elements:
            if await element.is_visible():
                try:
                    await element.click(timeout=5_000)
                    clicked += 1
                    await page.wait_for_timeout(pause_ms)
                except Exception:
                    pass
    return clicked


class PlaywrightPageRenderer:
    def __init__(
        self,
        *,
        user_agent: str = "LGHomeStyleBot/1.0",
        viewport: dict[str, int] | None = None,
    ) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._user_agent = user_agent
        self._viewport = viewport or {"width": 1440, "height": 1024}

    async def render_page(self, url: str) -> str:
        page = await self._new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            await _expand_collapsed_sections(page)
            return await page.content()
        except TimeoutError as error:
            raise RenderPageError(f"Timed out rendering page: {url}") from error
        except Error as error:
            raise RenderPageError(f"Failed to render page: {url}") from error
        finally:
            await page.close()

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def _new_page(self) -> Page:
        browser = await self._get_browser()
        return await browser.new_page(
            user_agent=self._user_agent,
            viewport=self._viewport,
        )

    async def _get_browser(self) -> Browser:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch()
        return self._browser
