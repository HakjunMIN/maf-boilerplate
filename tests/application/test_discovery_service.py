from pathlib import Path

import pytest

from homestyle_ingestion.application.discovery import DiscoveryConfigurationError, DiscoveryService
from homestyle_ingestion.domain.discovery import DiscoveredUrl, DiscoveryBootstrap


def write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "discovery.toml"
    config_path.write_text(
        "\n".join(
            [
                "[discovery]",
                'locale = "ko"',
                'allowed_hosts = ["homestyle.lge.co.kr"]',
                'allowed_url_prefixes = ["/home", "/collection", "/shop?"]',
            ]
        ),
        encoding="utf-8",
    )
    return config_path


@pytest.mark.asyncio
async def test_discover_from_robots_reads_sitemap_index_then_discovers_urls(tmp_path: Path) -> None:
    responses = {
        "https://homestyle.lge.co.kr/robots.txt": """
            User-agent: *
            Allow: /
            Crawl-delay: 0.5
            Sitemap: https://static-store.lge.co.kr/sitemap/sitemap.xml
        """,
        "https://static-store.lge.co.kr/sitemap/sitemap.xml": """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap>
                <loc>https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml</loc>
              </sitemap>
            </sitemapindex>
        """,
        "https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url>
                <loc>https://homestyle.lge.co.kr/home</loc>
              </url>
            </urlset>
        """,
    }

    async def fetch_text(url: str) -> str:
        return responses[url]

    service = DiscoveryService(fetch_text=fetch_text)

    bootstrap = await service.discover_from_robots(
        robots_url="https://homestyle.lge.co.kr/robots.txt",
        config_path=write_config(tmp_path),
    )

    assert bootstrap == DiscoveryBootstrap(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        crawl_delay_seconds=0.5,
        discovered_urls=[
            DiscoveredUrl(
                url="https://homestyle.lge.co.kr/home",
                locale="ko",
                lastmod=None,
                source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
            )
        ],
    )


@pytest.mark.asyncio
async def test_discover_from_robots_fails_when_sitemap_entrypoint_is_missing(tmp_path: Path) -> None:
    async def fetch_text(_: str) -> str:
        return """
            User-agent: *
            Allow: /
        """

    service = DiscoveryService(fetch_text=fetch_text)

    with pytest.raises(
        DiscoveryConfigurationError,
        match="robots.txt must declare a Sitemap entrypoint.",
    ):
        await service.discover_from_robots(
            robots_url="https://homestyle.lge.co.kr/robots.txt",
            config_path=write_config(tmp_path),
        )


@pytest.mark.asyncio
async def test_discover_returns_only_allowlisted_homestyle_urls(tmp_path: Path) -> None:
    responses = {
        "https://static-store.lge.co.kr/sitemap/sitemap.xml": """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap>
                <loc>https://homestyle.lge.co.kr/sitemap/sitemap_product-list.xml</loc>
              </sitemap>
              <sitemap>
                <loc>https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml</loc>
              </sitemap>
            </sitemapindex>
        """,
        "https://homestyle.lge.co.kr/sitemap/sitemap_product-list.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url>
                <loc>https://homestyle.lge.co.kr/shop?superCategoryId=2506000003</loc>
              </url>
              <url>
                <loc>https://homestyle.lge.co.kr/search?q=bed</loc>
              </url>
              <url>
                <loc>https://www.lge.co.kr/not-in-scope</loc>
              </url>
            </urlset>
        """,
        "https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url>
                <loc>https://homestyle.lge.co.kr/home</loc>
              </url>
              <url>
                <loc>https://homestyle.lge.co.kr/collection</loc>
              </url>
            </urlset>
        """,
    }

    async def fetch_text(url: str) -> str:
        return responses[url]

    service = DiscoveryService(fetch_text=fetch_text)

    discovered_urls = await service.discover(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
    )

    assert discovered_urls == [
        DiscoveredUrl(
            url="https://homestyle.lge.co.kr/shop?superCategoryId=2506000003",
            locale="ko",
            lastmod=None,
            source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_product-list.xml",
        ),
        DiscoveredUrl(
            url="https://homestyle.lge.co.kr/home",
            locale="ko",
            lastmod=None,
            source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
        ),
        DiscoveredUrl(
            url="https://homestyle.lge.co.kr/collection",
            locale="ko",
            lastmod=None,
            source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
        ),
    ]


@pytest.mark.asyncio
async def test_discover_keeps_lastmod_and_source_sitemap(tmp_path: Path) -> None:
    responses = {
        "https://static-store.lge.co.kr/sitemap/sitemap.xml": """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap>
                <loc>https://homestyle.lge.co.kr/sitemap/sitemap_event.xml</loc>
              </sitemap>
            </sitemapindex>
        """,
        "https://homestyle.lge.co.kr/sitemap/sitemap_event.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url>
                <loc>https://homestyle.lge.co.kr/shop?superCategoryId=2506000004</loc>
                <lastmod>2026-04-20</lastmod>
              </url>
              <url>
                <loc>https://homestyle.lge.co.kr/home</loc>
              </url>
            </urlset>
        """,
    }

    async def fetch_text(url: str) -> str:
        return responses[url]

    service = DiscoveryService(fetch_text=fetch_text)

    discovered_urls = await service.discover(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
    )

    assert discovered_urls == [
        DiscoveredUrl(
            url="https://homestyle.lge.co.kr/shop?superCategoryId=2506000004",
            locale="ko",
            lastmod="2026-04-20",
            source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_event.xml",
        ),
        DiscoveredUrl(
            url="https://homestyle.lge.co.kr/home",
            locale="ko",
            lastmod=None,
            source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_event.xml",
        ),
    ]
