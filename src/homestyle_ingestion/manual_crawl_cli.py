import argparse
import asyncio
from pathlib import Path

from homestyle_ingestion.application.discovery import DiscoveryService
from homestyle_ingestion.application.ingestion import IngestionPipeline
from homestyle_ingestion.application.manual_crawl import ManualCrawlService, SelectionMode
from homestyle_ingestion.infrastructure.fetch import ManagedPageFetcher, build_page_fetcher
from homestyle_ingestion.infrastructure.rendering import PlaywrightPageRenderer
from homestyle_ingestion.infrastructure.storage import LocalPageStore


def main() -> None:
    asyncio.run(_main_async())


async def _main_async() -> None:
    args = _parse_args()
    await _run_manual_crawl(
        robots_url=args.robots_url,
        config_path=args.config,
        output_directory=args.output_dir,
        max_urls=args.max_urls,
        selection_mode=args.selection_mode,
        extraction_version=args.extraction_version,
        user_agent=args.user_agent,
    )


async def _run_manual_crawl(
    *,
    robots_url: str,
    config_path: Path,
    output_directory: Path,
    max_urls: int,
    selection_mode: SelectionMode,
    extraction_version: str,
    user_agent: str,
) -> None:
    page_fetcher = build_page_fetcher(user_agent=user_agent)
    renderer = PlaywrightPageRenderer(user_agent=user_agent)
    page_store = LocalPageStore(root_directory=output_directory)
    try:
        service = ManualCrawlService(
            bootstrap_discovery=DiscoveryService(
                fetch_text=_build_fetch_text(page_fetcher),
            ).discover_from_robots,
            run_ingestion=IngestionPipeline(
                fetch_text=_build_fetch_text(page_fetcher),
                fetch_page=page_fetcher.fetch_page,
                render_page=renderer.render_page,
                save_page=page_store.save_page,
                extraction_version=extraction_version,
                index_sections=_noop_index_sections,
            ).run_discovered,
            list_stored_pages=page_store.list_pages,
        )
        result = await service.crawl_sample(
            robots_url=robots_url,
            config_path=config_path,
            max_urls=max_urls,
            selection_mode=selection_mode,
        )
    finally:
        await renderer.close()
        await page_fetcher.close()

    print(
        f"Discovered {result.discovered_count} URLs, crawled {result.selected_count}, "
        f"saved to {output_directory}"
    )
    print(f"Sitemap index: {result.sitemap_index_url}")
    for url in result.selected_urls:
        print(url)


def _build_fetch_text(page_fetcher: ManagedPageFetcher) -> callable:
    async def fetch_text(url: str) -> str:
        response = await page_fetcher.fetch_page(url, {})
        if response.body is None:
            raise ValueError(f"Expected text body for discovery URL: {url}")
        return response.body

    return fetch_text


async def _noop_index_sections(sections: list[object]) -> None:
    _ = sections


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl a limited Homestyle sample for manual testing.")
    parser.add_argument("robots_url")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/discovery.toml"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".manual-crawl"),
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--selection-mode",
        choices=("sequential", "random"),
        default="sequential",
    )
    parser.add_argument(
        "--extraction-version",
        default="manual-v1",
    )
    parser.add_argument(
        "--user-agent",
        default="LGHomeStyleBot/1.0",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
