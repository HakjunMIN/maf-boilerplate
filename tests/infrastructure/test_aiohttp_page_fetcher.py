from collections.abc import AsyncIterator

import aiohttp
import asyncio
import pytest
import pytest_asyncio
from aiohttp import web

from homestyle_ingestion.domain.fetch import FetchExecutionError, FetchResponse
from homestyle_ingestion.infrastructure.fetch import (
    AioHttpPageFetcher,
    ResilientPageFetcher,
    ThrottledPageFetcher,
    build_page_fetcher,
)


@pytest_asyncio.fixture
async def local_page_server(unused_tcp_port: int) -> AsyncIterator[tuple[str, dict[str, str]]]:
    observed_headers: dict[str, str] = {}

    async def handle(request: web.Request) -> web.Response:
        observed_headers["User-Agent"] = request.headers["User-Agent"]
        if "If-None-Match" in request.headers:
            observed_headers["If-None-Match"] = request.headers["If-None-Match"]
        return web.Response(
            text="ok",
            headers={
                "ETag": '"etag-1"',
                "Last-Modified": "Mon, 21 Apr 2026 00:00:00 GMT",
            },
        )

    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()

    try:
        yield f"http://127.0.0.1:{unused_tcp_port}/", observed_headers
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_fetch_page_sends_project_user_agent_and_returns_fetch_response(
    local_page_server: tuple[str, dict[str, str]],
) -> None:
    url, observed_headers = local_page_server

    fetcher = AioHttpPageFetcher(user_agent="LGHomeStyleBot/1.0")

    try:
        response = await fetcher.fetch_page(url, headers={"If-None-Match": '"etag-0"'})
    finally:
        await fetcher.close()

    assert observed_headers == {
        "User-Agent": "LGHomeStyleBot/1.0",
        "If-None-Match": '"etag-0"',
    }
    assert response == FetchResponse(
        status_code=200,
        body="ok",
        etag='"etag-1"',
        last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
    )


@pytest.mark.asyncio
async def test_resilient_fetch_page_retries_with_backoff_then_returns_response() -> None:
    attempts = 0
    sleep_delays: list[float] = []

    async def fetch_once(url: str, headers: dict[str, str]) -> FetchResponse:
        nonlocal attempts
        attempts += 1
        assert url == "https://homestyle.lge.co.kr/home"
        assert headers == {"If-None-Match": '"etag-1"'}
        if attempts < 3:
            raise aiohttp.ClientError("temporary failure")
        return FetchResponse(
            status_code=200,
            body="ok",
            etag='"etag-2"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        )

    async def sleep(delay: float) -> None:
        sleep_delays.append(delay)

    fetcher = ResilientPageFetcher(
        fetch_once=fetch_once,
        sleep=sleep,
        max_attempts=3,
        base_delay_seconds=0.5,
        jitter_ratio=0.1,
        random_fraction=lambda: 0.0,
    )

    response = await fetcher.fetch_page(
        "https://homestyle.lge.co.kr/home",
        headers={"If-None-Match": '"etag-1"'},
    )

    assert attempts == 3
    assert sleep_delays == [0.5, 1.0]
    assert response == FetchResponse(
        status_code=200,
        body="ok",
        etag='"etag-2"',
        last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
    )


@pytest.mark.asyncio
async def test_resilient_fetch_page_raises_fetch_execution_error_after_max_attempts() -> None:
    attempts = 0
    sleep_delays: list[float] = []

    async def fetch_once(_: str, __: dict[str, str]) -> FetchResponse:
        nonlocal attempts
        attempts += 1
        raise aiohttp.ClientError("temporary failure")

    async def sleep(delay: float) -> None:
        sleep_delays.append(delay)

    fetcher = ResilientPageFetcher(
        fetch_once=fetch_once,
        sleep=sleep,
        max_attempts=3,
        base_delay_seconds=0.5,
        jitter_ratio=0.1,
        random_fraction=lambda: 0.0,
    )

    with pytest.raises(FetchExecutionError, match="Fetch failed after 3 attempts."):
        await fetcher.fetch_page("https://homestyle.lge.co.kr/home", headers={})

    assert attempts == 3
    assert sleep_delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_throttled_fetch_page_limits_maximum_concurrency_to_five() -> None:
    in_flight = 0
    max_in_flight = 0
    release_fetches = asyncio.Event()

    async def fetch_once(_: str, __: dict[str, str]) -> FetchResponse:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await release_fetches.wait()
        in_flight -= 1
        return FetchResponse(status_code=200, body="ok", etag=None, last_modified=None)

    fetcher = ThrottledPageFetcher(
        fetch_once=fetch_once,
        min_delay_seconds=0.0,
        max_concurrency=5,
    )

    tasks = [
        asyncio.create_task(fetcher.fetch_page(f"https://homestyle.lge.co.kr/home/{index}", headers={}))
        for index in range(6)
    ]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    release_fetches.set()
    responses = await asyncio.gather(*tasks)

    assert max_in_flight == 5
    assert len(responses) == 6


@pytest.mark.asyncio
async def test_throttled_fetch_page_waits_before_starting_the_next_request() -> None:
    started_at: list[float] = []
    current_time = 10.0
    sleep_delays: list[float] = []

    async def fetch_once(_: str, __: dict[str, str]) -> FetchResponse:
        started_at.append(current_time)
        return FetchResponse(status_code=200, body="ok", etag=None, last_modified=None)

    async def sleep(delay: float) -> None:
        nonlocal current_time
        sleep_delays.append(delay)
        current_time += delay

    fetcher = ThrottledPageFetcher(
        fetch_once=fetch_once,
        min_delay_seconds=0.5,
        max_concurrency=5,
        sleep=sleep,
        monotonic=lambda: current_time,
    )

    await fetcher.fetch_page("https://homestyle.lge.co.kr/home/1", headers={})
    await fetcher.fetch_page("https://homestyle.lge.co.kr/home/2", headers={})

    assert started_at == [10.0, 10.5]
    assert sleep_delays == [0.5]


@pytest.mark.asyncio
async def test_build_page_fetcher_retries_http_failures_then_returns_response(
    unused_tcp_port: int,
) -> None:
    attempts = 0

    async def handle(_: web.Request) -> web.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return web.Response(status=503, text="temporary failure")
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()

    fetcher = build_page_fetcher(
        user_agent="LGHomeStyleBot/1.0",
        min_delay_seconds=0.0,
        max_concurrency=5,
        max_attempts=3,
        base_delay_seconds=0.0,
        jitter_ratio=0.0,
    )

    try:
        response = await fetcher.fetch_page(f"http://127.0.0.1:{unused_tcp_port}/", headers={})
    finally:
        await fetcher.close()
        await runner.cleanup()

    assert attempts == 3
    assert response == FetchResponse(status_code=200, body="ok", etag=None, last_modified=None)
