from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from aiohttp import web
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from homestyle_ingestion.infrastructure.rendering import PlaywrightPageRenderer, RenderPageError


@pytest_asyncio.fixture
async def rendered_page_server(unused_tcp_port: int) -> AsyncIterator[str]:
    async def handle(_: web.Request) -> web.Response:
        return web.Response(
            text="""
                <html>
                  <body>
                    <main id="content">초기 상태</main>
                    <script>
                      document.getElementById("content").textContent = "렌더 완료";
                    </script>
                  </body>
                </html>
            """,
            content_type="text/html",
        )

    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()

    try:
        yield f"http://127.0.0.1:{unused_tcp_port}/"
    finally:
        await runner.cleanup()


@pytest_asyncio.fixture
async def expandable_page_server(unused_tcp_port: int) -> AsyncIterator[str]:
        async def handle(_: web.Request) -> web.Response:
                return web.Response(
                        text="""
                                <html>
                                    <body>
                                        <button id=\"expand\">더보기</button>
                                        <section id=\"details\" hidden>펼쳐진 상세 정보</section>
                                        <script>
                                            document.getElementById("expand").addEventListener("click", () => {
                                                document.getElementById("details").hidden = false;
                                                document.getElementById("expand").remove();
                                            });
                                        </script>
                                    </body>
                                </html>
                        """,
                        content_type="text/html",
                )

        app = web.Application()
        app.router.add_get("/", handle)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
        await site.start()

        try:
                yield f"http://127.0.0.1:{unused_tcp_port}/"
        finally:
                await runner.cleanup()


@pytest.mark.asyncio
async def test_render_page_returns_final_rendered_html(rendered_page_server: str) -> None:
    renderer = PlaywrightPageRenderer()

    try:
        html = await renderer.render_page(rendered_page_server)
    finally:
        await renderer.close()

    assert "렌더 완료" in html
    assert "초기 상태" not in html


@pytest.mark.asyncio
async def test_render_page_expands_collapsed_sections_before_returning_html(
    expandable_page_server: str,
) -> None:
    renderer = PlaywrightPageRenderer()

    try:
        html = await renderer.render_page(expandable_page_server)
    finally:
        await renderer.close()

    assert "펼쳐진 상세 정보" in html
    assert 'id="expand"' not in html


@pytest.mark.asyncio
async def test_render_page_surfaces_timeout_as_render_page_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        async def goto(self, url: str, wait_until: str) -> None:
            assert url == "https://homestyle.lge.co.kr/home"
            assert wait_until == "networkidle"
            raise PlaywrightTimeoutError("timed out")

        async def query_selector_all(self, selector: str) -> list[object]:
            assert selector
            return []

        async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
            return None

        async def wait_for_timeout(self, _: int) -> None:
            return None

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_page(self, **_: object) -> FakePage:
            return FakePage()

        async def close(self) -> None:
            return None

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = self

        async def launch(self) -> FakeBrowser:
            return FakeBrowser()

        async def stop(self) -> None:
            return None

    class FakeAsyncPlaywright:
        async def start(self) -> FakePlaywright:
            return FakePlaywright()

    monkeypatch.setattr(
        "homestyle_ingestion.infrastructure.rendering.async_playwright",
        lambda: FakeAsyncPlaywright(),
    )

    renderer = PlaywrightPageRenderer()

    with pytest.raises(RenderPageError, match="Timed out rendering page: https://homestyle.lge.co.kr/home"):
        await renderer.render_page("https://homestyle.lge.co.kr/home")

    await renderer.close()


@pytest.mark.asyncio
async def test_render_page_opens_page_with_default_viewport_and_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_new_page_kwargs: dict[str, object] = {}

    class FakePage:
        async def goto(self, url: str, wait_until: str) -> None:
            assert url == "https://homestyle.lge.co.kr/home"
            assert wait_until == "networkidle"

        async def query_selector_all(self, selector: str) -> list[object]:
            assert selector
            return []

        async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
            return None

        async def wait_for_timeout(self, _: int) -> None:
            return None

        async def content(self) -> str:
            return "<html><body><main>렌더 완료</main></body></html>"

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_page(self, **kwargs: object) -> FakePage:
            observed_new_page_kwargs.update(kwargs)
            return FakePage()

        async def close(self) -> None:
            return None

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = self

        async def launch(self) -> FakeBrowser:
            return FakeBrowser()

        async def stop(self) -> None:
            return None

    class FakeAsyncPlaywright:
        async def start(self) -> FakePlaywright:
            return FakePlaywright()

    monkeypatch.setattr(
        "homestyle_ingestion.infrastructure.rendering.async_playwright",
        lambda: FakeAsyncPlaywright(),
    )

    renderer = PlaywrightPageRenderer()

    try:
        html = await renderer.render_page("https://homestyle.lge.co.kr/home")
    finally:
        await renderer.close()

    assert "렌더 완료" in html
    assert observed_new_page_kwargs == {
        "user_agent": "LGHomeStyleBot/1.0",
        "viewport": {"width": 1440, "height": 1024},
    }


@pytest.mark.asyncio
async def test_render_page_ignores_expand_click_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    clicked_selectors: list[str] = []

    class FakeElement:
        async def is_visible(self) -> bool:
            return True

        async def click(self, timeout: int) -> None:
            assert timeout == 5_000
            raise RuntimeError("click failed")

    class FakePage:
        async def goto(self, url: str, wait_until: str) -> None:
            assert url == "https://homestyle.lge.co.kr/home"
            assert wait_until == "networkidle"

        async def query_selector_all(self, selector: str) -> list[FakeElement]:
            clicked_selectors.append(selector)
            if selector == "text=더보기":
                return [FakeElement()]
            return []

        async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
            return None

        async def wait_for_timeout(self, _: int) -> None:
            return None

        async def content(self) -> str:
            return "<html><body><main>렌더 완료</main></body></html>"

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_page(self, **_: object) -> FakePage:
            return FakePage()

        async def close(self) -> None:
            return None

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = self

        async def launch(self) -> FakeBrowser:
            return FakeBrowser()

        async def stop(self) -> None:
            return None

    class FakeAsyncPlaywright:
        async def start(self) -> FakePlaywright:
            return FakePlaywright()

    monkeypatch.setattr(
        "homestyle_ingestion.infrastructure.rendering.async_playwright",
        lambda: FakeAsyncPlaywright(),
    )

    renderer = PlaywrightPageRenderer()

    try:
        html = await renderer.render_page("https://homestyle.lge.co.kr/home")
    finally:
        await renderer.close()

    assert "렌더 완료" in html
    assert clicked_selectors[:2] == ["text=상품정보 더보기", "text=더보기"]
