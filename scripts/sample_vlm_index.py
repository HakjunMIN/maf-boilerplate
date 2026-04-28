from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = REPO_ROOT / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

load_dotenv(REPO_ROOT / ".env")

from homestyle_ingestion.application.discovery import DiscoveryService
from homestyle_ingestion.application.ingestion import IngestionPipeline
from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.fetch import FetchMetadata
from homestyle_ingestion.domain.vlm import ImageCandidate
from homestyle_ingestion.infrastructure.fetch import ManagedPageFetcher, build_page_fetcher
from homestyle_ingestion.infrastructure.rendering import PlaywrightPageRenderer
from homestyle_ingestion.infrastructure.storage import LocalPageStore
from homestyle_shared.domain.indexing import SectionDocument
from homestyle_shared.infrastructure.azure_identity import build_azure_credential
from homestyle_shared.infrastructure.openai import AzureOpenAIEmbedder, AzureOpenAIVisionExtractor


def main() -> None:
    asyncio.run(_main_async())


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set. Check your .env file.")
    return value


async def _main_async() -> None:
    args = _parse_args()

    openai_endpoint = _require_env("AZURE_OPENAI_ENDPOINT")
    openai_api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-07-01-preview")
    embedding_deployment = _require_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    vision_deployment = _require_env("AZURE_OPENAI_VISION_DEPLOYMENT")
    search_endpoint = _require_env("AZURE_SEARCH_ENDPOINT")
    search_index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "homestyle-sections-sample")

    output_directory = args.output_dir.resolve()
    markdown_directory = output_directory / "markdown"
    review_directory = output_directory / "review"
    page_store = LocalPageStore(root_directory=output_directory / "pages")

    credential = build_azure_credential(use_developer_credentials=True)
    embedder = AzureOpenAIEmbedder(
        endpoint=openai_endpoint,
        deployment=embedding_deployment,
        api_version=openai_api_version,
        credential=credential,
    )
    vision_extractor = AzureOpenAIVisionExtractor(
        endpoint=openai_endpoint,
        deployment=vision_deployment,
        api_version=openai_api_version,
        credential=credential,
    )

    await _ensure_search_index(
        endpoint=search_endpoint,
        index_name=search_index_name,
        credential=credential,
    )
    search_admin_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "").strip()
    search_credential = AzureKeyCredential(search_admin_key) if search_admin_key else credential
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=search_index_name,
        credential=search_credential,
    )

    page_fetcher = build_page_fetcher(user_agent=args.user_agent)
    renderer = PlaywrightPageRenderer(user_agent=args.user_agent)
    discovered_image_urls: dict[str, list[str]] = {}
    indexed_chunks: list[str] = []

    async def fetch_text(url: str) -> str:
        response = await page_fetcher.fetch_page(url, {})
        if response.body is None:
            raise ValueError(f"Expected discovery body for {url}")
        return response.body

    async def extract_image_candidates(url: str, html: str) -> tuple[ImageCandidate, ...]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[ImageCandidate] = []
        image_urls: list[str] = []
        for element in soup.find_all("img"):
            if not isinstance(element, Tag):
                continue
            src = (
                element.get("src")
                or element.get("data-src")
                or element.get("data-lazy-src")
                or element.get("data-original")
            )
            if not isinstance(src, str) or not src.strip():
                continue
            image_url = urljoin(url, src.strip())
            parsed = urlparse(image_url)
            if parsed.scheme not in {"http", "https"}:
                continue
            width = _coerce_width(element.get("width"))
            role = element.get("role")
            aria_hidden = str(element.get("aria-hidden", "false")).lower() == "true"
            candidates.append(
                ImageCandidate(
                    width=width,
                    role=role if isinstance(role, str) else None,
                    aria_hidden=aria_hidden,
                )
            )
            image_urls.append(image_url)
        discovered_image_urls[url] = image_urls
        return tuple(candidates)

    async def enrich_page(page: ExtractedPage, image_candidates: tuple[ImageCandidate, ...]) -> ExtractedPage:
        image_urls = discovered_image_urls.get(page.url, [])[:5]
        meaningful_image_urls = [
            image_url
            for image_url, image_candidate in zip(image_urls, image_candidates, strict=False)
            if image_candidate.width >= 200 and image_candidate.role != "presentation" and not image_candidate.aria_hidden
        ]
        if not meaningful_image_urls:
            return page

        prompt = (
            "You are extracting product-detail markdown from LG Homestyle page images. "
            "Return concise Korean markdown that captures visible product facts, materials, dimensions, colors, pricing, options, and promotional text. "
            "Do not invent missing information."
        )
        vlm_markdown = await vision_extractor.extract_markdown(prompt, meaningful_image_urls)
        if not vlm_markdown:
            return page

        dom_segment = ExtractedSegment(
            segment_id=f"{page.url}#dom-1",
            markdown=page.markdown,
        )
        vlm_segment = ExtractedSegment(
            segment_id=f"{page.url}#vlm-1",
            markdown=vlm_markdown,
            source_kind="vlm",
            confidence_score=0.85,
            review_state="not_required",
            is_image_derived=True,
        )
        combined_markdown = page.markdown.strip()
        if combined_markdown:
            combined_markdown = f"{combined_markdown}\n\n{vlm_markdown.strip()}"
        else:
            combined_markdown = vlm_markdown.strip()

        return ExtractedPage(
            url=page.url,
            title=page.title,
            breadcrumb=page.breadcrumb,
            markdown=combined_markdown,
            segments=(dom_segment, vlm_segment),
        )

    async def save_page(page: ExtractedPage, metadata: FetchMetadata, extraction_version: str) -> None:
        await page_store.save_page(page, metadata, extraction_version)
        markdown_directory.mkdir(parents=True, exist_ok=True)
        markdown_path = markdown_directory / f"{_page_slug(page.url)}.md"
        markdown_path.write_text(page.markdown, encoding="utf-8")
        manifest_path = markdown_directory / f"{_page_slug(page.url)}.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "url": page.url,
                    "title": page.title,
                    "breadcrumb": list(page.breadcrumb),
                    "segments": [
                        {
                            "segment_id": segment.segment_id,
                            "source_kind": segment.source_kind,
                            "confidence_score": segment.confidence_score,
                            "review_state": segment.review_state,
                            "is_image_derived": segment.is_image_derived,
                        }
                        for segment in page.segments
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _safe_key(chunk_id: str) -> str:
        return base64.urlsafe_b64encode(chunk_id.encode()).decode().rstrip("=")

    async def index_sections(sections: list[SectionDocument]) -> None:
        documents = []
        for section in sections:
            indexed_chunks.append(section.chunk_id)
            documents.append(
                {
                    "chunk_id": _safe_key(section.chunk_id),
                    "page_url": section.page_url,
                    "locale": section.locale,
                    "title": section.title,
                    "breadcrumb": list(section.breadcrumb),
                    "section_heading": section.section_heading,
                    "content": section.content,
                    "content_vector": await embedder.embed_text(section.content),
                    "confidence_score": section.confidence_score,
                    "is_image_derived": section.is_image_derived,
                    "extraction_version": section.extraction_version,
                    "reviewer_approved": section.reviewer_approved,
                    "is_deleted": False,
                    "deleted_at": None,
                }
            )
        if documents:
            await search_client.merge_or_upload_documents(documents)

    try:
        bootstrap = await DiscoveryService(fetch_text=fetch_text).discover_from_robots(
            args.robots_url,
            args.config,
        )
        selected_urls = bootstrap.discovered_urls[: args.max_urls]
        previous_metadata_by_url = {
            stored_page.url: stored_page.metadata
            for stored_page in await page_store.list_pages()
            if stored_page.url in {discovered_url.url for discovered_url in selected_urls}
        }
        sections = await IngestionPipeline(
            fetch_text=fetch_text,
            fetch_page=page_fetcher.fetch_page,
            render_page=renderer.render_page,
            save_page=save_page,
            extract_image_candidates=extract_image_candidates,
            enrich_page=enrich_page,
            extraction_version=args.extraction_version,
            index_sections=index_sections,
        ).run_discovered(
            discovered_urls=selected_urls,
            previous_metadata_by_url=previous_metadata_by_url,
        )
    finally:
        await search_client.close()
        await embedder.close()
        await vision_extractor.close()
        await renderer.close()
        await page_fetcher.close()

    review_directory.mkdir(parents=True, exist_ok=True)
    (review_directory / "run-summary.json").write_text(
        json.dumps(
            {
                "selected_urls": [discovered_url.url for discovered_url in selected_urls],
                "indexed_chunk_ids": indexed_chunks,
                "section_count": len(sections),
                "markdown_directory": str(markdown_directory),
                "page_store_directory": str((output_directory / "pages").resolve()),
                "search_endpoint": search_endpoint,
                "search_index_name": search_index_name,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved page payloads to {(output_directory / 'pages').resolve()}")
    print(f"Saved markdown files to {markdown_directory.resolve()}")
    print(f"Indexed {len(indexed_chunks)} chunks into {search_index_name}")
    print(f"Processed {len(selected_urls)} product URLs from {bootstrap.sitemap_index_url}")


def _coerce_width(value: object) -> int:
    if isinstance(value, str):
        digits = "".join(character for character in value if character.isdigit())
        if digits:
            return int(digits)
    return 400


def _page_slug(url: str) -> str:
    product_ids = parse_qs(urlparse(url).query).get("productId", [])
    if product_ids and product_ids[0].strip():
        return product_ids[0].strip()
    return urlparse(url).path.strip("/").replace("/", "-") or "page"


async def _ensure_search_index(*, endpoint: str, index_name: str, credential: object) -> None:
    import urllib.request as _urllib_request

    token = credential.get_token("https://search.azure.com/.default")  # type: ignore[union-attr]
    index_definition = {
        "name": index_name,
        "fields": [
            {"name": "chunk_id", "type": "Edm.String", "key": True, "searchable": False, "filterable": True, "retrievable": True, "sortable": True, "facetable": False},
            {"name": "page_url", "type": "Edm.String", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "locale", "type": "Edm.String", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": True},
            {"name": "title", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "breadcrumb", "type": "Collection(Edm.String)", "searchable": True, "filterable": False, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "section_heading", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "content", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "content_vector", "type": "Collection(Edm.Single)", "searchable": True, "filterable": False, "retrievable": False, "sortable": False, "facetable": False, "dimensions": 1536, "vectorSearchProfile": "content-vector-profile"},
            {"name": "confidence_score", "type": "Edm.Double", "searchable": False, "filterable": True, "retrievable": True, "sortable": True, "facetable": False},
            {"name": "is_image_derived", "type": "Edm.Boolean", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": True},
            {"name": "extraction_version", "type": "Edm.String", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": True},
            {"name": "reviewer_approved", "type": "Edm.Boolean", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": True},
            {"name": "is_deleted", "type": "Edm.Boolean", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": True},
            {"name": "deleted_at", "type": "Edm.String", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": False},
        ],
        "vectorSearch": {
            "algorithms": [
                {
                    "name": "content-vector-algorithm",
                    "kind": "hnsw",
                    "hnswParameters": {"metric": "cosine", "m": 4, "efConstruction": 400, "efSearch": 500},
                }
            ],
            "profiles": [
                {
                    "name": "content-vector-profile",
                    "algorithm": "content-vector-algorithm",
                }
            ],
        },
        "semantic": {
            "defaultConfiguration": "default-semantic",
            "configurations": [
                {
                    "name": "default-semantic",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "prioritizedContentFields": [{"fieldName": "content"}],
                        "prioritizedKeywordsFields": [{"fieldName": "section_heading"}],
                    },
                }
            ],
        },
    }
    import urllib.request as _urllib_request
    request = _urllib_request.Request(
        url=f"{endpoint.rstrip('/')}/indexes/{index_name}?api-version=2023-11-01",
        data=json.dumps(index_definition).encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token.token}"},
    )
    with _urllib_request.urlopen(request, timeout=60) as response:
        response.read()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a 10-page Homestyle sample crawl with VLM markdown enrichment and Azure Search indexing.")
    parser.add_argument("--robots-url", default="https://homestyle.lge.co.kr/robots.txt")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "discovery.toml")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / ".sample-vlm-crawl")
    parser.add_argument("--max-urls", type=int, default=10)
    parser.add_argument("--user-agent", default="LGHomeStyleBot/1.0")
    parser.add_argument("--extraction-version", default="sample-vlm-v1")
    return parser.parse_args()


if __name__ == "__main__":
    main()