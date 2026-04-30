from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredUrl:
    url: str
    locale: str
    lastmod: str | None
    source_sitemap_url: str


@dataclass(frozen=True)
class DiscoveryConfig:
    locale: str
    allowed_hosts: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryBootstrap:
    sitemap_index_url: str
    crawl_delay_seconds: float | None
    discovered_urls: list[DiscoveredUrl]
