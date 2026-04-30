from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from homestyle_ingestion.domain.discovery import DiscoveredUrl
from homestyle_ingestion.domain.fetch import FetchMetadata
from homestyle_shared.domain.indexing import SectionDocument
from homestyle_shared.infrastructure.observability import (
    StructuredLogger,
    bind_correlation_id,
    build_logger,
)

RunnerMode = Literal["full", "incremental"]

DiscoverUrls = Callable[[str, Path], Awaitable[list[DiscoveredUrl]]]
RunIngestion = Callable[..., Awaitable[list[SectionDocument]]]
ListStoredPages = Callable[[], Awaitable[Sequence["StoredPageInventoryRecord"]]]
MarkDeleted = Callable[[str, str], Awaitable[None]]
DeletePage = Callable[[str], Awaitable[None]]
SoftDeletePage = Callable[[str, str], Awaitable[None]]
HardDeletePage = Callable[[str], Awaitable[None]]


class StoredPageInventoryRecord(Protocol):
    url: str
    metadata: FetchMetadata
    is_deleted: bool
    deleted_at: str | None


@dataclass(frozen=True)
class PipelineRunResult:
    mode: RunnerMode
    discovered_count: int
    indexed_section_count: int
    soft_deleted_urls: tuple[str, ...] = ()
    hard_deleted_urls: tuple[str, ...] = ()


class PipelineRunner:
    def __init__(
        self,
        *,
        discover_urls: DiscoverUrls,
        run_ingestion: RunIngestion,
        list_stored_pages: ListStoredPages,
        mark_deleted: MarkDeleted,
        delete_page: DeletePage,
        soft_delete_page: SoftDeletePage,
        hard_delete_page: HardDeletePage,
        hard_delete_grace_period: timedelta = timedelta(days=7),
        now: Callable[[], datetime] | None = None,
        logger: StructuredLogger | None = None,
    ) -> None:
        self._discover_urls = discover_urls
        self._run_ingestion = run_ingestion
        self._list_stored_pages = list_stored_pages
        self._mark_deleted = mark_deleted
        self._delete_page = delete_page
        self._soft_delete_page = soft_delete_page
        self._hard_delete_page = hard_delete_page
        self._hard_delete_grace_period = hard_delete_grace_period
        self._now = now or (lambda: datetime.now(UTC))
        self._logger = logger or build_logger("pipeline_runner")

    async def run(
        self,
        *,
        sitemap_index_url: str,
        config_path: Path,
        mode: RunnerMode = "incremental",
        correlation_id: str | None = None,
    ) -> PipelineRunResult:
        logger, resolved_correlation_id = bind_correlation_id(self._logger, correlation_id)
        stored_pages = {
            stored_page.url: stored_page for stored_page in await self._list_stored_pages()
        }
        discovered_urls = await self._discover_urls(sitemap_index_url, config_path)
        discovered_url_set = {discovered_url.url for discovered_url in discovered_urls}
        previous_metadata_by_url = self._build_previous_metadata(
            mode=mode,
            stored_pages=stored_pages,
            discovered_url_set=discovered_url_set,
        )
        sections = await self._run_ingestion(
            discovered_urls=discovered_urls,
            previous_metadata_by_url=previous_metadata_by_url,
        )
        soft_deleted_urls, hard_deleted_urls = await self._process_missing_pages(
            stored_pages=stored_pages,
            discovered_url_set=discovered_url_set,
        )
        result = PipelineRunResult(
            mode=mode,
            discovered_count=len(discovered_urls),
            indexed_section_count=len(sections),
            soft_deleted_urls=soft_deleted_urls,
            hard_deleted_urls=hard_deleted_urls,
        )
        logger.info(
            "pipeline_run_completed",
            mode=mode,
            pages_discovered=result.discovered_count,
            pages_crawled=result.discovered_count,
            pages_changed=0,
            pages_unchanged=0,
            pages_failed=0,
            vlm_calls=0,
            vlm_failures=0,
            vlm_low_confidence_count=0,
            index_docs_upserted=result.indexed_section_count,
            index_docs_deleted=len(result.soft_deleted_urls) + len(result.hard_deleted_urls),
        )
        return result

    def _build_previous_metadata(
        self,
        *,
        mode: RunnerMode,
        stored_pages: dict[str, StoredPageInventoryRecord],
        discovered_url_set: set[str],
    ) -> dict[str, FetchMetadata]:
        if mode == "full":
            return {}
        return {
            url: stored_pages[url].metadata
            for url in discovered_url_set
            if url in stored_pages
        }

    async def _process_missing_pages(
        self,
        *,
        stored_pages: dict[str, StoredPageInventoryRecord],
        discovered_url_set: set[str],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        soft_deleted_urls: list[str] = []
        hard_deleted_urls: list[str] = []
        current_timestamp = self._now()
        deleted_at = current_timestamp.isoformat()

        for url, stored_page in stored_pages.items():
            if url in discovered_url_set:
                continue
            if not stored_page.is_deleted:
                await self._soft_delete_page(url, deleted_at)
                await self._mark_deleted(url, deleted_at)
                soft_deleted_urls.append(url)
                continue

            deleted_timestamp = self._parse_deleted_at(stored_page.deleted_at)
            if deleted_timestamp is None:
                continue
            if current_timestamp - deleted_timestamp < self._hard_delete_grace_period:
                continue

            await self._hard_delete_page(url)
            await self._delete_page(url)
            hard_deleted_urls.append(url)

        return tuple(soft_deleted_urls), tuple(hard_deleted_urls)

    def _parse_deleted_at(self, deleted_at: str | None) -> datetime | None:
        if deleted_at is None:
            return None
        deleted_timestamp = datetime.fromisoformat(deleted_at)
        if deleted_timestamp.tzinfo is None:
            return deleted_timestamp.replace(tzinfo=UTC)
        return deleted_timestamp.astimezone(UTC)
