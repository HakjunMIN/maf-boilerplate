from __future__ import annotations
import mimetypes

from aiohttp import ClientSession, ClientTimeout

import argparse
import asyncio
import base64
import json
import os
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from openai import BadRequestError

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = REPO_ROOT / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

_SUPPORTED_IMAGE_CONTENT_TYPES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}

load_dotenv(REPO_ROOT / ".env")

from homestyle_ingestion.application.discovery import DiscoveryService  # noqa: E402
from homestyle_ingestion.application.ingestion import IngestionPipeline  # noqa: E402
from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment  # noqa: E402
from homestyle_ingestion.domain.fetch import FetchMetadata  # noqa: E402
from homestyle_ingestion.domain.vlm import ImageCandidate  # noqa: E402
from homestyle_ingestion.infrastructure.fetch import build_page_fetcher  # noqa: E402
from homestyle_ingestion.infrastructure.rendering import PlaywrightPageRenderer  # noqa: E402
from homestyle_ingestion.infrastructure.storage import LocalPageStore  # noqa: E402
from homestyle_shared.domain.indexing import SectionDocument  # noqa: E402
from homestyle_shared.infrastructure.azure_identity import build_azure_credential  # noqa: E402
from homestyle_shared.infrastructure.observability import bind_correlation_id, build_logger, configure_process_observability  # noqa: E402
from homestyle_shared.infrastructure.openai import AzureOpenAIEmbedder, AzureOpenAIVisionExtractor  # noqa: E402


logger = build_logger("sample_vlm_index")


def main() -> None:
    configure_process_observability(
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        application_insights_connection_string=os.environ.get(
            "APPLICATION_INSIGHTS_CONNECTION_STRING"
        ),
    )
    asyncio.run(_main_async())


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set. Check your .env file.")
    return value


async def _main_async() -> None:
    args = _parse_args()
    run_logger, _ = bind_correlation_id(logger)
    run_logger.info(
        "sample_vlm_index_started",
        robots_url=args.robots_url,
        max_urls=args.max_urls,
        extraction_version=args.extraction_version,
        output_dir=str(args.output_dir.resolve()),
    )

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

    run_logger.info("search_index_ensuring", search_endpoint=search_endpoint, search_index_name=search_index_name)
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
    image_session = ClientSession(timeout=ClientTimeout(total=30))
    discovered_image_urls: dict[str, list[str]] = {}
    indexed_chunks: list[str] = []

    async def fetch_text(url: str) -> str:
        response = await page_fetcher.fetch_page(url, {})
        if response.body is None:
            raise ValueError(f"Expected discovery body for {url}")
        return response.body

    async def extract_vlm_markdown(
        *,
        page_url: str,
        prompt: str,
        image_inputs: list[tuple[str, str]],
    ) -> str | None:
        data_urls = [data_url for _, data_url in image_inputs]
        try:
            return await vision_extractor.extract_markdown(prompt, data_urls)
        except BadRequestError as error:
            if not _is_content_policy_violation(error):
                raise
            run_logger.info(
                "vlm_batch_content_policy_violation",
                page_url=page_url,
                attempted_image_count=len(image_inputs),
                error=str(error),
            )

        safe_markdown_parts: list[str] = []
        skipped_image_count = 0
        for image_url, data_url in image_inputs:
            try:
                partial_markdown = await vision_extractor.extract_markdown(prompt, [data_url])
            except BadRequestError as error:
                if not _is_content_policy_violation(error):
                    raise
                skipped_image_count += 1
                run_logger.info(
                    "vlm_image_skipped",
                    page_url=page_url,
                    image_url=image_url,
                    reason="content_policy_violation",
                    error=str(error),
                )
                continue
            if partial_markdown:
                safe_markdown_parts.append(partial_markdown.strip())

        if not safe_markdown_parts:
            run_logger.info(
                "vlm_enrichment_skipped",
                page_url=page_url,
                reason="all_images_filtered_by_content_policy",
                skipped_image_count=skipped_image_count,
            )
            return None

        run_logger.info(
            "vlm_content_policy_fallback_completed",
            page_url=page_url,
            safe_image_count=len(safe_markdown_parts),
            skipped_image_count=skipped_image_count,
        )
        return "\n\n".join(markdown for markdown in safe_markdown_parts if markdown)

    async def extract_image_candidates(url: str, html: str) -> tuple[ImageCandidate, ...]:
        soup = BeautifulSoup(html, "lxml")
        product_detail_section = _find_product_detail_section(soup)
        if product_detail_section is None:
            run_logger.info("product_detail_section_not_found", page_url=url)
            discovered_image_urls[url] = []
            return ()

        candidates: list[ImageCandidate] = []
        image_urls: list[str] = []
        for element in product_detail_section.find_all("img"):
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
        run_logger.info(
            "product_detail_images_collected",
            page_url=url,
            image_count=len(image_urls),
        )
        return tuple(candidates)

    async def enrich_page(page: ExtractedPage, image_candidates: tuple[ImageCandidate, ...]) -> ExtractedPage:
        image_urls = discovered_image_urls.get(page.url, [])[: args.max_images_per_page]
        meaningful_image_urls = [
            image_url
            for image_url, image_candidate in zip(image_urls, image_candidates, strict=False)
            if image_candidate.width >= 200 and image_candidate.role != "presentation" and not image_candidate.aria_hidden
        ]
        if not meaningful_image_urls:
            return page

        run_logger.info(
            "vlm_enrichment_started",
            page_url=page.url,
            candidate_image_count=len(image_candidates),
            meaningful_image_count=len(meaningful_image_urls),
        )

        downloaded_image_inputs: list[tuple[str, str]] = []
        for image_url in meaningful_image_urls:
            data_url = await _download_image_as_data_url(
                image_session,
                image_url=image_url,
                referer=page.url,
                user_agent=args.user_agent,
                logger=run_logger,
            )
            if data_url is not None:
                downloaded_image_inputs.append((image_url, data_url))

        if not downloaded_image_inputs:
            run_logger.info("vlm_enrichment_skipped", page_url=page.url, reason="no_downloadable_images")
            return page

        prompt = (
            "You are extracting product-detail markdown from LG Homestyle page images. "
            "Return concise Korean markdown that captures visible product facts, materials, dimensions, colors, pricing, options, and promotional text. "
            "Do not invent missing information."
        )
        vlm_markdown = await extract_vlm_markdown(
            page_url=page.url,
            prompt=prompt,
            image_inputs=downloaded_image_inputs,
        )
        if vlm_markdown is None:
            return page
        if not vlm_markdown:
            run_logger.info("vlm_enrichment_skipped", page_url=page.url, reason="empty_vlm_markdown")
            return page

        run_logger.info(
            "vlm_enrichment_completed",
            page_url=page.url,
            downloaded_image_count=len(downloaded_image_inputs),
            markdown_length=len(vlm_markdown),
        )

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
        run_logger.info(
            "page_saved",
            page_url=page.url,
            segment_count=len(page.segments),
            markdown_path=str(markdown_path),
        )

    def _safe_key(chunk_id: str) -> str:
        return base64.urlsafe_b64encode(chunk_id.encode()).decode().rstrip("=")

    async def index_sections(sections: list[SectionDocument]) -> None:
        run_logger.info("search_indexing_started", batch_section_count=len(sections))
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
                    "content": section.content,
                    "content_vector": await embedder.embed_text(section.content),
                    "product_id": section.product_id,
                    "product_name": section.product_name,
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
        run_logger.info(
            "search_indexing_completed",
            batch_section_count=len(sections),
            indexed_chunk_count=len(indexed_chunks),
        )

    try:
        run_logger.info("discovery_started", config_path=str(args.config.resolve()))
        bootstrap = await DiscoveryService(fetch_text=fetch_text).discover_from_robots(
            args.robots_url,
            args.config,
        )
        selected_urls = bootstrap.discovered_urls[: args.max_urls]
        run_logger.info(
            "discovery_completed",
            sitemap_index_url=bootstrap.sitemap_index_url,
            discovered_url_count=len(bootstrap.discovered_urls),
            selected_url_count=len(selected_urls),
        )
        previous_metadata_by_url = {
            stored_page.url: stored_page.metadata
            for stored_page in await page_store.list_pages()
            if stored_page.url in {discovered_url.url for discovered_url in selected_urls}
        }
        run_logger.info(
            "ingestion_started",
            selected_url_count=len(selected_urls),
            previously_stored_count=len(previous_metadata_by_url),
        )
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
        run_logger.info(
            "ingestion_completed",
            selected_url_count=len(selected_urls),
            section_count=len(sections),
            indexed_chunk_count=len(indexed_chunks),
        )
    except Exception as exc:
        run_logger.info(
            "sample_vlm_index_failed",
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        raise
    finally:
        await search_client.close()
        await embedder.close()
        await vision_extractor.close()
        await image_session.close()
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
    run_logger.info(
        "sample_vlm_index_completed",
        selected_url_count=len(selected_urls),
        indexed_chunk_count=len(indexed_chunks),
        section_count=len(sections),
        review_summary_path=str((review_directory / "run-summary.json").resolve()),
    )

def _coerce_width(value: object) -> int:
    if isinstance(value, str):
        digits = "".join(character for character in value if character.isdigit())
        if digits:
            return int(digits)
    return 400


def _find_product_detail_section(soup: BeautifulSoup) -> Tag | None:
    section = soup.find(
        "section",
        attrs={"data-area": "홈스타일 PDP 상품상세 정보 영역"},
    )
    if isinstance(section, Tag):
        return section
    section = soup.find(
        lambda tag: isinstance(tag, Tag)
        and tag.name == "section"
        and any(
            isinstance(class_name, str) and class_name.startswith("PcProductDetailInfoV2_detailSection")
            for class_name in tag.get("class", [])
        ),
    )
    return section if isinstance(section, Tag) else None


def _is_content_policy_violation(error: Exception) -> bool:
    code = str(getattr(error, "code", "") or "").strip().lower()
    if code == "content_policy_violation":
        return True
    error_message = str(error).lower()
    return "content_policy_violation" in error_message or "content safety" in error_message


def _page_slug(url: str) -> str:
    product_ids = parse_qs(urlparse(url).query).get("productId", [])
    if product_ids and product_ids[0].strip():
        return product_ids[0].strip()
    return urlparse(url).path.strip("/").replace("/", "-") or "page"



async def _download_image_as_data_url(
    session: ClientSession,
    *,
    image_url: str,
    referer: str,
    user_agent: str,
    logger: object,
) -> str | None:
    headers = {
        "User-Agent": user_agent,
        "Referer": referer,
    }
    try:
        async with session.get(image_url, headers=headers) as response:
            if response.status >= 400:
                logger.info("image_download_failed", image_url=image_url, status=response.status)
                return None

            image_bytes = await response.read()
            if not image_bytes:
                logger.info("image_download_failed", image_url=image_url, reason="empty_response_body")
                return None

            response_content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
            guessed_content_type, _ = mimetypes.guess_type(image_url)
            content_type = (
                _sniff_supported_content_type(image_bytes)
                or _normalize_content_type(response_content_type)
                or _normalize_content_type(guessed_content_type)
            )
            if content_type not in _SUPPORTED_IMAGE_CONTENT_TYPES:
                logger.info(
                    "image_download_failed",
                    image_url=image_url,
                    reason="unsupported_content_type",
                    content_type=content_type,
                )
                return None

            encoded = base64.b64encode(image_bytes).decode("ascii")
            return f"data:{content_type};base64,{encoded}"
    except Exception as exc:
        logger.info(
            "image_download_failed",
            image_url=image_url,
            reason="request_exception",
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        return None


def _normalize_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    normalized = content_type.strip().lower()
    if normalized == "image/jpg":
        return "image/jpeg"
    return normalized


def _sniff_supported_content_type(image_bytes: bytes) -> str | None:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None

async def _ensure_search_index(*, endpoint: str, index_name: str, credential: object) -> None:
    import urllib.request as _urllib_request

    token = await credential.get_token("https://search.azure.com/.default")  # type: ignore[union-attr]
    index_definition = {
        "name": index_name,
        "fields": [
            {"name": "chunk_id", "type": "Edm.String", "key": True, "searchable": False, "filterable": True, "retrievable": True, "sortable": True, "facetable": False},
            {"name": "page_url", "type": "Edm.String", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "product_id", "type": "Edm.String", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "product_name", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "locale", "type": "Edm.String", "searchable": False, "filterable": True, "retrievable": True, "sortable": False, "facetable": True},
            {"name": "title", "type": "Edm.String", "searchable": True, "filterable": False, "retrievable": True, "sortable": False, "facetable": False},
            {"name": "breadcrumb", "type": "Collection(Edm.String)", "searchable": True, "filterable": False, "retrievable": True, "sortable": False, "facetable": False},
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
                        "prioritizedKeywordsFields": [{"fieldName": "product_name"}],
                    },
                }
            ],
        },
    }
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
    parser.add_argument(
        "--max-images-per-page",
        type=int,
        default=10,
        help="상품정보 섹션에서 VLM에 전달할 최대 이미지 수.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()