from pathlib import Path

import pytest

from homestyle_ingestion.application.manual_crawl import ManualCrawlResult, ManualCrawlService
from homestyle_ingestion.domain.discovery import DiscoveredUrl, DiscoveryBootstrap
from homestyle_ingestion.domain.fetch import FetchMetadata


@pytest.mark.asyncio
async def test_manual_crawl_service_selects_first_ten_urls_for_sequential_sample(
    tmp_path: Path,
) -> None:
    discovered_urls = [
        DiscoveredUrl(
            url=f"https://homestyle.lge.co.kr/item?productId=G25070000{210 + index}",
            locale="ko",
            lastmod=None,
            source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_product.xml",
        )
        for index in range(12)
    ]
    captured_discovered_urls: list[DiscoveredUrl] = []
    captured_previous_metadata: dict[str, FetchMetadata] = {}

    async def bootstrap_discovery(robots_url: str, config_path: Path) -> DiscoveryBootstrap:
        assert robots_url == "https://homestyle.lge.co.kr/robots.txt"
        assert config_path == tmp_path / "discovery.toml"
        return DiscoveryBootstrap(
            sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
            crawl_delay_seconds=2.0,
            discovered_urls=discovered_urls,
        )

    async def run_ingestion(
        *,
        discovered_urls: list[DiscoveredUrl],
        previous_metadata_by_url: dict[str, FetchMetadata],
    ) -> list[object]:
        captured_discovered_urls.extend(discovered_urls)
        captured_previous_metadata.update(previous_metadata_by_url)
        return []

    class StoredPage:
        def __init__(self, url: str) -> None:
            self.url = url
            self.metadata = FetchMetadata(
                url=url,
                etag='"etag-1"',
                last_modified=None,
                content_hash="hash-1",
            )

    async def list_stored_pages() -> list[StoredPage]:
        return [
            StoredPage("https://homestyle.lge.co.kr/item?productId=G25070000210"),
            StoredPage("https://homestyle.lge.co.kr/item?productId=G25070000221"),
        ]

    service = ManualCrawlService(
        bootstrap_discovery=bootstrap_discovery,
        run_ingestion=run_ingestion,
        list_stored_pages=list_stored_pages,
    )

    result = await service.crawl_sample(
        robots_url="https://homestyle.lge.co.kr/robots.txt",
        config_path=tmp_path / "discovery.toml",
        max_urls=10,
        selection_mode="sequential",
    )

    assert result == ManualCrawlResult(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        discovered_count=12,
        selected_count=10,
        selected_urls=tuple(url.url for url in discovered_urls[:10]),
    )
    assert captured_discovered_urls == discovered_urls[:10]
    assert captured_previous_metadata == {
        "https://homestyle.lge.co.kr/item?productId=G25070000210": FetchMetadata(
            url="https://homestyle.lge.co.kr/item?productId=G25070000210",
            etag='"etag-1"',
            last_modified=None,
            content_hash="hash-1",
        )
    }
