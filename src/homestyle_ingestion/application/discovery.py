from collections.abc import Awaitable, Callable
from pathlib import Path
import tomllib
from urllib.parse import urlparse
from xml.etree import ElementTree

from homestyle_ingestion.domain.discovery import DiscoveredUrl, DiscoveryBootstrap, DiscoveryConfig

FetchText = Callable[[str], Awaitable[str]]
_SITEMAP_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class DiscoveryConfigurationError(Exception):
    """Raised when discovery configuration is invalid."""


class DiscoveryService:
    def __init__(self, fetch_text: FetchText) -> None:
        self._fetch_text = fetch_text

    async def discover_from_robots(self, robots_url: str, config_path: Path) -> DiscoveryBootstrap:
        robots_txt = await self._fetch_text(robots_url)
        sitemap_index_url = self._parse_sitemap_index_url_from_robots(robots_txt)
        crawl_delay_seconds = self._parse_crawl_delay_from_robots(robots_txt)
        discovered_urls = await self.discover(sitemap_index_url=sitemap_index_url, config_path=config_path)
        return DiscoveryBootstrap(
            sitemap_index_url=sitemap_index_url,
            crawl_delay_seconds=crawl_delay_seconds,
            discovered_urls=discovered_urls,
        )

    async def discover(self, sitemap_index_url: str, config_path: Path) -> list[DiscoveredUrl]:
        config = self._load_config(config_path)
        discovered_urls: list[DiscoveredUrl] = []

        sitemap_index_xml = await self._fetch_text(sitemap_index_url)
        for sub_sitemap_url in self._parse_sitemap_index(sitemap_index_xml):
            urlset_xml = await self._fetch_text(sub_sitemap_url)
            for discovered_url in self._parse_urlset(urlset_xml, config, sub_sitemap_url):
                discovered_urls.append(discovered_url)

        return discovered_urls

    def _load_config(self, config_path: Path) -> DiscoveryConfig:
        with config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)

        discovery_config = raw_config.get("discovery")
        if not isinstance(discovery_config, dict):
            raise DiscoveryConfigurationError("Missing [discovery] configuration section.")

        locale = discovery_config.get("locale")
        allowed_hosts = discovery_config.get("allowed_hosts")
        allowed_url_prefixes = discovery_config.get("allowed_url_prefixes")

        if not isinstance(locale, str) or not locale:
            raise DiscoveryConfigurationError("discovery.locale must be a non-empty string.")
        if not self._is_string_list(allowed_hosts):
            raise DiscoveryConfigurationError("discovery.allowed_hosts must be a list of strings.")
        if not self._is_string_list(allowed_url_prefixes):
            raise DiscoveryConfigurationError(
                "discovery.allowed_url_prefixes must be a list of strings."
            )

        return DiscoveryConfig(
            locale=locale,
            allowed_hosts=tuple(allowed_hosts),
            allowed_url_prefixes=tuple(allowed_url_prefixes),
        )

    def _parse_sitemap_index(self, sitemap_index_xml: str) -> list[str]:
        root = ElementTree.fromstring(sitemap_index_xml)
        return [
            location.text.strip()
            for location in root.findall("./sm:sitemap/sm:loc", _SITEMAP_NAMESPACE)
            if location.text
        ]

    def _parse_sitemap_index_url_from_robots(self, robots_txt: str) -> str:
        for line in robots_txt.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip().lower() == "sitemap" and value.strip():
                return value.strip()
        raise DiscoveryConfigurationError("robots.txt must declare a Sitemap entrypoint.")

    def _parse_crawl_delay_from_robots(self, robots_txt: str) -> float | None:
        for line in robots_txt.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip().lower() == "crawl-delay" and value.strip():
                return float(value.strip())
        return None

    def _parse_urlset(
        self,
        urlset_xml: str,
        config: DiscoveryConfig,
        source_sitemap_url: str,
    ) -> list[DiscoveredUrl]:
        root = ElementTree.fromstring(urlset_xml)
        discovered_urls: list[DiscoveredUrl] = []

        for url_element in root.findall("./sm:url", _SITEMAP_NAMESPACE):
            location = url_element.find("./sm:loc", _SITEMAP_NAMESPACE)
            if location is None or not location.text:
                continue

            url = location.text.strip()
            if not self._is_allowed_url(url, config):
                continue

            lastmod = url_element.find("./sm:lastmod", _SITEMAP_NAMESPACE)
            discovered_urls.append(
                DiscoveredUrl(
                    url=url,
                    locale=config.locale,
                    lastmod=lastmod.text.strip() if lastmod is not None and lastmod.text else None,
                    source_sitemap_url=source_sitemap_url,
                )
            )

        return discovered_urls

    def _is_allowed_url(self, url: str, config: DiscoveryConfig) -> bool:
        parsed_url = urlparse(url)
        if parsed_url.hostname not in config.allowed_hosts:
            return False

        path_with_query = parsed_url.path
        if parsed_url.query:
            path_with_query = f"{path_with_query}?{parsed_url.query}"

        return any(path_with_query.startswith(prefix) for prefix in config.allowed_url_prefixes)

    def _is_string_list(self, value: object) -> bool:
        return isinstance(value, list) and all(isinstance(item, str) and item for item in value)
