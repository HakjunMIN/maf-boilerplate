from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from homestyle_ingestion.application.ingestion import IngestionPipeline
from homestyle_ingestion.application.runner import PipelineRunResult, PipelineRunner
from homestyle_ingestion.domain.discovery import DiscoveredUrl
from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_ingestion.domain.fetch import FetchMetadata, FetchResponse
from homestyle_ingestion.infrastructure.storage import LocalPageStore
from homestyle_shared.domain.indexing import SectionDocument


async def noop_mark_deleted(_: str, __: str) -> None:
    return None


async def noop_delete_page(_: str) -> None:
    return None


def build_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "discovery.toml"
    config_path.write_text(
        "\n".join(
            [
                "[discovery]",
                'locale = "ko"',
                'allowed_hosts = ["homestyle.lge.co.kr"]',
                'allowed_url_prefixes = ["/collection"]',
            ]
        ),
        encoding="utf-8",
    )
    return config_path


async def save_page(store: LocalPageStore, *, url: str, etag: str) -> None:
    await store.save_page(
        ExtractedPage(
            url=url,
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            markdown="# 거실 컬렉션",
        ),
        FetchMetadata(
            url=url,
            etag=etag,
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
            content_hash="hash-1",
        ),
        "v1",
    )


@pytest.mark.asyncio
async def test_pipeline_runner_full_mode_reingests_without_previous_metadata(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path / "pages")
    discovered_url = DiscoveredUrl(
        url="https://homestyle.lge.co.kr/collection/living-room",
        locale="ko",
        lastmod=None,
        source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
    )
    captured_previous_metadata: dict[str, FetchMetadata] = {}

    await save_page(store, url=discovered_url.url, etag='"etag-previous"')

    async def discover_urls(_: str, __: Path) -> list[DiscoveredUrl]:
        return [discovered_url]

    async def run_ingestion(
        *,
        discovered_urls: list[DiscoveredUrl],
        previous_metadata_by_url: dict[str, FetchMetadata],
    ) -> list[SectionDocument]:
        assert discovered_urls == [discovered_url]
        captured_previous_metadata.update(previous_metadata_by_url)
        return [
            SectionDocument(
                chunk_id=f"{discovered_url.url}#section-1",
                page_url=discovered_url.url,
                locale="ko",
                title="거실 컬렉션",
                breadcrumb=("collection", "living-room"),
                section_heading="거실 제안",
                content="## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
            )
        ]

    runner = PipelineRunner(
        discover_urls=discover_urls,
        run_ingestion=run_ingestion,
        list_stored_pages=store.list_pages,
        mark_deleted=noop_mark_deleted,
        delete_page=noop_delete_page,
        soft_delete_page=noop_mark_deleted,
        hard_delete_page=noop_delete_page,
    )

    result = await runner.run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=build_config(tmp_path),
        mode="full",
    )

    assert captured_previous_metadata == {}
    assert result == PipelineRunResult(
        mode="full",
        discovered_count=1,
        indexed_section_count=1,
    )


@pytest.mark.asyncio
async def test_pipeline_runner_incremental_mode_reuses_stored_fetch_metadata(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path / "pages")
    discovered_url = DiscoveredUrl(
        url="https://homestyle.lge.co.kr/collection/living-room",
        locale="ko",
        lastmod=None,
        source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
    )
    expected_metadata = FetchMetadata(
        url=discovered_url.url,
        etag='"etag-previous"',
        last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        content_hash="hash-1",
    )
    captured_previous_metadata: dict[str, FetchMetadata] = {}

    await save_page(store, url=discovered_url.url, etag='"etag-previous"')

    async def discover_urls(_: str, __: Path) -> list[DiscoveredUrl]:
        return [discovered_url]

    async def run_ingestion(
        *,
        discovered_urls: list[DiscoveredUrl],
        previous_metadata_by_url: dict[str, FetchMetadata],
    ) -> list[SectionDocument]:
        assert discovered_urls == [discovered_url]
        captured_previous_metadata.update(previous_metadata_by_url)
        return []

    runner = PipelineRunner(
        discover_urls=discover_urls,
        run_ingestion=run_ingestion,
        list_stored_pages=store.list_pages,
        mark_deleted=noop_mark_deleted,
        delete_page=noop_delete_page,
        soft_delete_page=noop_mark_deleted,
        hard_delete_page=noop_delete_page,
    )

    result = await runner.run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=build_config(tmp_path),
    )

    assert captured_previous_metadata == {discovered_url.url: expected_metadata}
    assert result == PipelineRunResult(
        mode="incremental",
        discovered_count=1,
        indexed_section_count=0,
    )


@pytest.mark.asyncio
async def test_pipeline_runner_soft_deletes_missing_pages_and_persists_tombstone(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path / "pages")
    missing_url = "https://homestyle.lge.co.kr/collection/missing-page"
    deleted_at = datetime(2026, 4, 28, tzinfo=UTC)
    soft_deleted_pages: list[tuple[str, str]] = []

    await save_page(store, url=missing_url, etag='"etag-previous"')

    async def discover_urls(_: str, __: Path) -> list[DiscoveredUrl]:
        return []

    async def run_ingestion(
        *,
        discovered_urls: list[DiscoveredUrl],
        previous_metadata_by_url: dict[str, FetchMetadata],
    ) -> list[SectionDocument]:
        assert discovered_urls == []
        assert previous_metadata_by_url == {}
        return []

    async def soft_delete_page(url: str, timestamp: str) -> None:
        soft_deleted_pages.append((url, timestamp))

    runner = PipelineRunner(
        discover_urls=discover_urls,
        run_ingestion=run_ingestion,
        list_stored_pages=store.list_pages,
        mark_deleted=store.mark_deleted,
        delete_page=store.delete_page,
        soft_delete_page=soft_delete_page,
        hard_delete_page=noop_delete_page,
        now=lambda: deleted_at,
    )

    result = await runner.run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=build_config(tmp_path),
    )

    inventory = await store.list_pages()

    assert soft_deleted_pages == [(missing_url, deleted_at.isoformat())]
    assert len(inventory) == 1
    assert inventory[0].url == missing_url
    assert inventory[0].is_deleted is True
    assert inventory[0].deleted_at == deleted_at.isoformat()
    assert result == PipelineRunResult(
        mode="incremental",
        discovered_count=0,
        indexed_section_count=0,
        soft_deleted_urls=(missing_url,),
    )


@pytest.mark.asyncio
async def test_pipeline_runner_hard_deletes_pages_after_grace_period(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path / "pages")
    missing_url = "https://homestyle.lge.co.kr/collection/missing-page"
    now = datetime(2026, 5, 5, tzinfo=UTC)
    hard_deleted_pages: list[str] = []

    await save_page(store, url=missing_url, etag='"etag-previous"')
    await store.mark_deleted(missing_url, (now - timedelta(days=8)).isoformat())

    async def discover_urls(_: str, __: Path) -> list[DiscoveredUrl]:
        return []

    async def run_ingestion(
        *,
        discovered_urls: list[DiscoveredUrl],
        previous_metadata_by_url: dict[str, FetchMetadata],
    ) -> list[SectionDocument]:
        assert discovered_urls == []
        assert previous_metadata_by_url == {}
        return []

    async def hard_delete_page(url: str) -> None:
        hard_deleted_pages.append(url)

    runner = PipelineRunner(
        discover_urls=discover_urls,
        run_ingestion=run_ingestion,
        list_stored_pages=store.list_pages,
        mark_deleted=store.mark_deleted,
        delete_page=store.delete_page,
        soft_delete_page=noop_mark_deleted,
        hard_delete_page=hard_delete_page,
        now=lambda: now,
    )

    result = await runner.run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=build_config(tmp_path),
    )

    assert hard_deleted_pages == [missing_url]
    assert await store.list_pages() == []
    assert result == PipelineRunResult(
        mode="incremental",
        discovered_count=0,
        indexed_section_count=0,
        hard_deleted_urls=(missing_url,),
    )


@pytest.mark.asyncio
async def test_pipeline_runner_hard_deletes_pages_at_seven_day_boundary(tmp_path: Path) -> None:
    store = LocalPageStore(root_directory=tmp_path / "pages")
    missing_url = "https://homestyle.lge.co.kr/collection/missing-page"
    now = datetime(2026, 5, 5, tzinfo=UTC)
    hard_deleted_pages: list[str] = []

    await save_page(store, url=missing_url, etag='"etag-previous"')
    await store.mark_deleted(missing_url, (now - timedelta(days=7)).isoformat())

    async def discover_urls(_: str, __: Path) -> list[DiscoveredUrl]:
        return []

    async def run_ingestion(
        *,
        discovered_urls: list[DiscoveredUrl],
        previous_metadata_by_url: dict[str, FetchMetadata],
    ) -> list[SectionDocument]:
        assert discovered_urls == []
        assert previous_metadata_by_url == {}
        return []

    async def hard_delete_page(url: str) -> None:
        hard_deleted_pages.append(url)

    runner = PipelineRunner(
        discover_urls=discover_urls,
        run_ingestion=run_ingestion,
        list_stored_pages=store.list_pages,
        mark_deleted=store.mark_deleted,
        delete_page=store.delete_page,
        soft_delete_page=noop_mark_deleted,
        hard_delete_page=hard_delete_page,
        now=lambda: now,
    )

    result = await runner.run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=build_config(tmp_path),
    )

    assert hard_deleted_pages == [missing_url]
    assert await store.list_pages() == []
    assert result == PipelineRunResult(
        mode="incremental",
        discovered_count=0,
        indexed_section_count=0,
        hard_deleted_urls=(missing_url,),
    )


@pytest.mark.asyncio
async def test_pipeline_runner_incremental_mode_uses_real_ingestion_services_with_storage_and_delete_seams(
    tmp_path: Path,
) -> None:
    store = LocalPageStore(root_directory=tmp_path / "pages")
    live_url = "https://homestyle.lge.co.kr/collection/living-room"
    missing_url = "https://homestyle.lge.co.kr/collection/missing-page"
    fetch_headers: list[dict[str, str]] = []
    indexed_sections: list[SectionDocument] = []
    soft_deleted_pages: list[tuple[str, str]] = []
    deleted_at = datetime(2026, 4, 28, tzinfo=UTC)

    await save_page(store, url=live_url, etag='"etag-live"')
    await save_page(store, url=missing_url, etag='"etag-missing"')

    discovered_url = DiscoveredUrl(
        url=live_url,
        locale="ko",
        lastmod=None,
        source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
    )

    async def discover_urls(_: str, __: Path) -> list[DiscoveredUrl]:
        return [discovered_url]

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == live_url
        fetch_headers.append(headers)
        return FetchResponse(
            status_code=200,
            body="""
                <html>
                  <body>
                    <main>
                      <h1>거실 컬렉션</h1>
                      <section>
                        <h2>거실 제안</h2>
                        <p>밝은 톤의 거실 스타일링입니다.</p>
                      </section>
                    </main>
                  </body>
                </html>
            """,
            etag='"etag-live-next"',
            last_modified="Tue, 22 Apr 2026 00:00:00 GMT",
        )

    async def index_sections(sections: list[SectionDocument]) -> None:
        indexed_sections.extend(sections)

    async def soft_delete_page(url: str, timestamp: str) -> None:
        soft_deleted_pages.append((url, timestamp))

    async def fetch_text(_: str) -> str:
        raise AssertionError("discovery is supplied by runner")

    pipeline = IngestionPipeline(
        fetch_text=fetch_text,
        fetch_page=fetch_page,
        save_page=store.save_page,
        index_sections=index_sections,
    )

    runner = PipelineRunner(
        discover_urls=discover_urls,
        run_ingestion=pipeline.run_discovered,
        list_stored_pages=store.list_pages,
        mark_deleted=store.mark_deleted,
        delete_page=store.delete_page,
        soft_delete_page=soft_delete_page,
        hard_delete_page=noop_delete_page,
        now=lambda: deleted_at,
    )

    result = await runner.run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=build_config(tmp_path),
    )

    inventory = {entry.url: entry for entry in await store.list_pages()}

    assert fetch_headers == [
        {
            "If-None-Match": '"etag-live"',
            "If-Modified-Since": "Mon, 21 Apr 2026 00:00:00 GMT",
        }
    ]
    assert indexed_sections == [
        SectionDocument(
            chunk_id=f"{live_url}#section-1",
            page_url=live_url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
        )
    ]
    assert soft_deleted_pages == [(missing_url, deleted_at.isoformat())]
    assert inventory[live_url].is_deleted is False
    assert inventory[live_url].metadata == FetchMetadata(
        url=live_url,
        etag='"etag-live-next"',
        last_modified="Tue, 22 Apr 2026 00:00:00 GMT",
        content_hash="hash-1",
        fetch_failed=False,
    )
    assert inventory[missing_url].is_deleted is True
    assert inventory[missing_url].deleted_at == deleted_at.isoformat()
    assert result == PipelineRunResult(
        mode="incremental",
        discovered_count=1,
        indexed_section_count=1,
        soft_deleted_urls=(missing_url,),
    )
