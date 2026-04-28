from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Literal, Protocol

from homestyle_ingestion.domain.discovery import DiscoveredUrl, DiscoveryBootstrap
from homestyle_ingestion.domain.fetch import FetchMetadata

SelectionMode = Literal["sequential", "random"]
BootstrapDiscovery = Callable[[str, Path], Awaitable[DiscoveryBootstrap]]
RunDiscoveredIngestion = Callable[..., Awaitable[list[object]]]
ShuffleUrls = Callable[[list[DiscoveredUrl]], None]


class StoredPageInventoryRecord(Protocol):
    url: str
    metadata: FetchMetadata


ListStoredPages = Callable[[], Awaitable[Sequence[StoredPageInventoryRecord]]]


@dataclass(frozen=True)
class ManualCrawlResult:
    sitemap_index_url: str
    discovered_count: int
    selected_count: int
    selected_urls: tuple[str, ...]


class ManualCrawlService:
    def __init__(
        self,
        *,
        bootstrap_discovery: BootstrapDiscovery,
        run_ingestion: RunDiscoveredIngestion,
        list_stored_pages: ListStoredPages,
        shuffle_urls: ShuffleUrls | None = None,
    ) -> None:
        self._bootstrap_discovery = bootstrap_discovery
        self._run_ingestion = run_ingestion
        self._list_stored_pages = list_stored_pages
        self._shuffle_urls = shuffle_urls or Random().shuffle

    async def crawl_sample(
        self,
        *,
        robots_url: str,
        config_path: Path,
        max_urls: int = 10,
        selection_mode: SelectionMode = "sequential",
    ) -> ManualCrawlResult:
        bootstrap = await self._bootstrap_discovery(robots_url, config_path)
        selected_urls = self._select_urls(
            bootstrap.discovered_urls,
            max_urls=max_urls,
            selection_mode=selection_mode,
        )
        stored_pages = {
            stored_page.url: stored_page.metadata
            for stored_page in await self._list_stored_pages()
            if stored_page.url in {discovered_url.url for discovered_url in selected_urls}
        }
        await self._run_ingestion(
            discovered_urls=selected_urls,
            previous_metadata_by_url=stored_pages,
        )
        return ManualCrawlResult(
            sitemap_index_url=bootstrap.sitemap_index_url,
            discovered_count=len(bootstrap.discovered_urls),
            selected_count=len(selected_urls),
            selected_urls=tuple(discovered_url.url for discovered_url in selected_urls),
        )

    def _select_urls(
        self,
        discovered_urls: list[DiscoveredUrl],
        *,
        max_urls: int,
        selection_mode: SelectionMode,
    ) -> list[DiscoveredUrl]:
        selected_urls = list(discovered_urls)
        if selection_mode == "random":
            self._shuffle_urls(selected_urls)
        return selected_urls[:max_urls]
