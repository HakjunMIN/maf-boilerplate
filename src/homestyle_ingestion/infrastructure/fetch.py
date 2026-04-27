from collections.abc import Awaitable, Callable
import asyncio
import time

from aiohttp import ClientError, ClientSession

from homestyle_ingestion.domain.fetch import FetchExecutionError, FetchResponse

FetchOnce = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]
Sleep = Callable[[float], Awaitable[None]]


class AioHttpPageFetcher:
    def __init__(self, *, user_agent: str) -> None:
        self._session = ClientSession(headers={"User-Agent": user_agent})

    async def fetch_page(self, url: str, headers: dict[str, str]) -> FetchResponse:
        async with self._session.get(url, headers=headers) as response:
            if response.status >= 400:
                response.raise_for_status()
            return FetchResponse(
                status_code=response.status,
                body=await response.text(),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )

    async def close(self) -> None:
        await self._session.close()


class ResilientPageFetcher:
    def __init__(
        self,
        *,
        fetch_once: FetchOnce,
        sleep: Sleep = asyncio.sleep,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        jitter_ratio: float = 0.1,
        random_fraction: Callable[[], float] | None = None,
    ) -> None:
        self._fetch_once = fetch_once
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._jitter_ratio = jitter_ratio
        self._random_fraction = random_fraction or (lambda: 0.5)

    async def fetch_page(self, url: str, headers: dict[str, str]) -> FetchResponse:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await self._fetch_once(url, headers)
            except ClientError:
                if attempt == self._max_attempts:
                    raise FetchExecutionError(
                        f"Fetch failed after {self._max_attempts} attempts."
                    ) from None
                await self._sleep(self._delay_seconds_for_attempt(attempt))
        raise RuntimeError("unreachable")

    def _delay_seconds_for_attempt(self, attempt: int) -> float:
        base_delay = self._base_delay_seconds * (2 ** (attempt - 1))
        jitter = base_delay * self._jitter_ratio * self._random_fraction()
        return base_delay + jitter


class ThrottledPageFetcher:
    def __init__(
        self,
        *,
        fetch_once: FetchOnce,
        min_delay_seconds: float,
        max_concurrency: int,
        sleep: Sleep = asyncio.sleep,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._fetch_once = fetch_once
        self._min_delay_seconds = min_delay_seconds
        self._sleep = sleep
        self._monotonic = monotonic or time.monotonic
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._delay_lock = asyncio.Lock()
        self._last_started_at: float | None = None

    async def fetch_page(self, url: str, headers: dict[str, str]) -> FetchResponse:
        async with self._semaphore:
            await self._wait_for_turn()
            return await self._fetch_once(url, headers)

    async def _wait_for_turn(self) -> None:
        async with self._delay_lock:
            if self._last_started_at is not None:
                elapsed = self._monotonic() - self._last_started_at
                remaining_delay = self._min_delay_seconds - elapsed
                if remaining_delay > 0:
                    await self._sleep(remaining_delay)
            self._last_started_at = self._monotonic()


class ManagedPageFetcher:
    def __init__(
        self,
        *,
        fetch_page: FetchOnce,
        close: Callable[[], Awaitable[None]],
    ) -> None:
        self._fetch_page = fetch_page
        self._close = close

    async def fetch_page(self, url: str, headers: dict[str, str]) -> FetchResponse:
        return await self._fetch_page(url, headers)

    async def close(self) -> None:
        await self._close()


def build_page_fetcher(
    *,
    user_agent: str,
    min_delay_seconds: float = 0.5,
    max_concurrency: int = 5,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    jitter_ratio: float = 0.1,
) -> ManagedPageFetcher:
    base_fetcher = AioHttpPageFetcher(user_agent=user_agent)
    resilient_fetcher = ResilientPageFetcher(
        fetch_once=base_fetcher.fetch_page,
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
        jitter_ratio=jitter_ratio,
    )
    throttled_fetcher = ThrottledPageFetcher(
        fetch_once=resilient_fetcher.fetch_page,
        min_delay_seconds=min_delay_seconds,
        max_concurrency=max_concurrency,
    )
    return ManagedPageFetcher(
        fetch_page=throttled_fetcher.fetch_page,
        close=base_fetcher.close,
    )
