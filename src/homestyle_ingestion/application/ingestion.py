from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path

from homestyle_ingestion.application.discovery import DiscoveryService, FetchText
from homestyle_ingestion.application.extraction import DomExtractionService
from homestyle_ingestion.application.fetch import ConditionalFetchService, FetchPage
from homestyle_ingestion.application.indexing import SectionSplitter
from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_ingestion.domain.fetch import FetchMetadata
from homestyle_ingestion.domain.rendering import RenderPageError
from homestyle_ingestion.domain.vlm import ImageCandidate
from homestyle_shared.domain.indexing import SectionDocument

IndexSections = Callable[[list[SectionDocument]], Awaitable[None]]
RenderPage = Callable[[str], Awaitable[str]]
SavePage = Callable[[ExtractedPage, FetchMetadata, str], Awaitable[None]]
ExtractImageCandidates = Callable[[str, str], Awaitable[tuple[ImageCandidate, ...]]]
EnrichPage = Callable[[ExtractedPage, tuple[ImageCandidate, ...]], Awaitable[ExtractedPage]]


class IngestionPipeline:
    def __init__(
        self,
        *,
        fetch_text: FetchText,
        fetch_page: FetchPage,
        render_page: RenderPage | None = None,
        save_page: SavePage | None = None,
        extract_image_candidates: ExtractImageCandidates | None = None,
        enrich_page: EnrichPage | None = None,
        extraction_version: str = "v1",
        index_sections: IndexSections,
    ) -> None:
        self._discovery_service = DiscoveryService(fetch_text=fetch_text)
        self._fetch_service = ConditionalFetchService(fetch_page=fetch_page)
        self._extraction_service = DomExtractionService()
        self._section_splitter = SectionSplitter()
        self._render_page = render_page
        self._save_page = save_page
        self._extract_image_candidates = extract_image_candidates
        self._enrich_page = enrich_page
        self._extraction_version = extraction_version
        self._index_sections = index_sections

    async def run(
        self,
        *,
        sitemap_index_url: str,
        config_path: Path,
        previous_metadata_by_url: Mapping[str, FetchMetadata],
    ) -> list[SectionDocument]:
        discovered_urls = await self._discovery_service.discover(
            sitemap_index_url=sitemap_index_url,
            config_path=config_path,
        )

        sections: list[SectionDocument] = []
        for discovered_url in discovered_urls:
            previous_metadata = previous_metadata_by_url.get(
                discovered_url.url,
                FetchMetadata(
                    url=discovered_url.url,
                    etag=None,
                    last_modified=None,
                    content_hash=None,
                ),
            )
            fetch_result = await self._fetch_service.fetch(
                discovered_url=discovered_url,
                previous_metadata=previous_metadata,
            )
            if fetch_result.body is None:
                continue

            html = fetch_result.body
            if self._render_page is not None:
                try:
                    html = await self._render_page(discovered_url.url)
                except RenderPageError:
                    continue

            page = self._extraction_service.extract(
                url=discovered_url.url,
                html=html,
            )
            if self._extract_image_candidates is not None and self._enrich_page is not None:
                image_candidates = await self._extract_image_candidates(discovered_url.url, html)
                page = await self._enrich_page(page, image_candidates)
            if self._save_page is not None:
                await self._save_page(page, fetch_result.metadata, self._extraction_version)
            sections.extend(self._section_splitter.split(page=page, locale=discovered_url.locale))

        if sections:
            await self._index_sections(sections)
        return sections
