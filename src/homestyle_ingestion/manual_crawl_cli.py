import argparse
import asyncio
import base64
import mimetypes
import os
from pathlib import Path
from typing import cast
from urllib.parse import urljoin, urlparse

from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup, Tag
from openai import BadRequestError

from homestyle_ingestion.application.discovery import DiscoveryService, FetchText
from homestyle_ingestion.application.ingestion import IngestionPipeline
from homestyle_ingestion.application.manual_crawl import ListStoredPages, ManualCrawlService, RunDiscoveredIngestion, SelectionMode
from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.vlm import ImageCandidate
from homestyle_ingestion.infrastructure.fetch import ManagedPageFetcher, build_page_fetcher
from homestyle_ingestion.infrastructure.rendering import PlaywrightPageRenderer
from homestyle_ingestion.infrastructure.storage import LocalPageStore
from homestyle_shared.domain.indexing import SectionDocument
from homestyle_shared.infrastructure.azure_identity import build_azure_credential
from homestyle_shared.infrastructure.observability import configure_process_observability
from homestyle_shared.infrastructure.openai import AzureOpenAIVisionExtractor


_SUPPORTED_IMAGE_CONTENT_TYPES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def main() -> None:
    configure_process_observability(
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        application_insights_connection_string=os.environ.get(
            "APPLICATION_INSIGHTS_CONNECTION_STRING"
        ),
    )
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
    image_session: ClientSession | None = None
    vision_extractor: AzureOpenAIVisionExtractor | None = None
    extract_image_candidates = None
    enrich_page = None
    vlm_config = _resolve_vlm_config()
    if vlm_config is not None:
        endpoint, deployment, api_version = vlm_config
        vision_extractor = AzureOpenAIVisionExtractor(
            endpoint=endpoint,
            deployment=deployment,
            api_version=api_version,
            credential=build_azure_credential(use_developer_credentials=True),
        )
        image_session = ClientSession(timeout=ClientTimeout(total=30))
        discovered_image_urls: dict[str, tuple[str, ...]] = {}

        async def extract_image_candidates(url: str, html: str) -> tuple[ImageCandidate, ...]:
            candidates, image_urls = _extract_image_candidates_from_html(url, html)
            discovered_image_urls[url] = image_urls
            return candidates

        async def enrich_page(
            page: ExtractedPage,
            image_candidates: tuple[ImageCandidate, ...],
        ) -> ExtractedPage:
            image_urls = [
                image_url
                for image_url, image_candidate in zip(
                    discovered_image_urls.get(page.url, ()), image_candidates, strict=False
                )
                if image_candidate.width >= 200
                and image_candidate.role != "presentation"
                and image_candidate.aria_hidden is False
            ][:10]
            if not image_urls or vision_extractor is None or image_session is None:
                return page

            image_inputs: list[str] = []
            for image_url in image_urls:
                data_url = await _download_image_as_data_url(
                    image_session,
                    image_url=image_url,
                    referer=page.url,
                    user_agent=user_agent,
                )
                if data_url is not None:
                    image_inputs.append(data_url)

            if not image_inputs:
                print(f"[manual_crawl] VLM skip: no supported images after normalization for {page.url}")
                return page

            try:
                vlm_markdown = await vision_extractor.extract_markdown(
                    _build_vlm_prompt(page),
                    image_inputs,
                )
            except BadRequestError as error:
                if _is_content_policy_violation(error):
                    print(f"[manual_crawl] VLM skipped by content safety for {page.url}: {error}")
                    return page
                raise
            if not vlm_markdown:
                print(f"[manual_crawl] VLM returned empty markdown for {page.url}")
                return page

            base_segments = page.segments or (
                ExtractedSegment(
                    segment_id=f"{page.url}#dom-1",
                    markdown=page.markdown,
                ),
            )
            normalized_vlm_markdown = vlm_markdown.strip()
            print(f"[manual_crawl] VLM extracted {len(normalized_vlm_markdown.splitlines())} lines for {page.url}")
            combined_markdown = page.markdown.strip()
            if combined_markdown:
                combined_markdown = f"{combined_markdown}\n\n{normalized_vlm_markdown}"
            else:
                combined_markdown = normalized_vlm_markdown

            return ExtractedPage(
                url=page.url,
                title=page.title,
                breadcrumb=page.breadcrumb,
                markdown=combined_markdown,
                segments=(
                    *base_segments,
                    ExtractedSegment(
                        segment_id=f"{page.url}#vlm-1",
                        markdown=normalized_vlm_markdown,
                        source_kind="vlm",
                        confidence_score=0.85,
                        review_state="not_required",
                        is_image_derived=True,
                    ),
                ),
            )

    try:
        service = ManualCrawlService(
            bootstrap_discovery=DiscoveryService(
                fetch_text=_build_fetch_text(page_fetcher),
            ).discover_from_robots,
            run_ingestion=cast(
                RunDiscoveredIngestion,
                IngestionPipeline(
                fetch_text=_build_fetch_text(page_fetcher),
                fetch_page=page_fetcher.fetch_page,
                render_page=renderer.render_page,
                save_page=page_store.save_page,
                extract_image_candidates=extract_image_candidates,
                enrich_page=enrich_page,
                report_progress=_report_progress,
                extraction_version=extraction_version,
                index_sections=_noop_index_sections,
                ).run_discovered,
            ),
            list_stored_pages=cast(ListStoredPages, page_store.list_pages),
        )
        result = await service.crawl_sample(
            robots_url=robots_url,
            config_path=config_path,
            max_urls=max_urls,
            selection_mode=selection_mode,
        )
    finally:
        if image_session is not None:
            await image_session.close()
        if vision_extractor is not None:
            await vision_extractor.close()
        await renderer.close()
        await page_fetcher.close()

    print(
        f"Discovered {result.discovered_count} URLs, crawled {result.selected_count}, "
        f"saved to {output_directory}"
    )
    print(f"VLM enrichment: {'enabled' if vlm_config is not None else 'disabled'}")
    print(f"Sitemap index: {result.sitemap_index_url}")
    for url in result.selected_urls:
        print(url)


def _build_fetch_text(page_fetcher: ManagedPageFetcher) -> FetchText:
    async def fetch_text(url: str) -> str:
        response = await page_fetcher.fetch_page(url, {})
        if response.body is None:
            raise ValueError(f"Expected text body for discovery URL: {url}")
        return response.body

    return fetch_text


async def _noop_index_sections(sections: list[SectionDocument]) -> None:
    _ = sections


def _resolve_vlm_config() -> tuple[str, str, str] | None:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    deployment = os.environ.get("AZURE_OPENAI_VISION_DEPLOYMENT", "").strip()
    if not endpoint or not deployment:
        return None

    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-07-01-preview").strip()
    return endpoint, deployment, api_version or "2025-07-01-preview"


def _report_progress(current: int, total: int, url: str) -> None:
    print(f"[manual_crawl] [{current}/{total}] Processing {url}")


def _is_content_policy_violation(error: Exception) -> bool:
    code = str(getattr(error, "code", "") or "").strip().lower()
    if code == "content_policy_violation":
        return True
    return "content_policy_violation" in str(error).lower() or "content safety" in str(error).lower()


def _extract_image_candidates_from_html(
    url: str,
    html: str,
) -> tuple[tuple[ImageCandidate, ...], tuple[str, ...]]:
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

        role = element.get("role")
        candidates.append(
            ImageCandidate(
                width=_coerce_width(element.get("width")),
                role=role if isinstance(role, str) else None,
                aria_hidden=str(element.get("aria-hidden", "false")).lower() == "true",
            )
        )
        image_urls.append(image_url)

    return tuple(candidates), tuple(image_urls)


def _coerce_width(value: object) -> int:
    if isinstance(value, str):
        digits = "".join(character for character in value if character.isdigit())
        if digits:
            return int(digits)
    if isinstance(value, int):
        return value
    return 400


async def _download_image_as_data_url(
    session: ClientSession,
    *,
    image_url: str,
    referer: str,
    user_agent: str,
) -> str | None:
    headers = {
        "User-Agent": user_agent,
        "Referer": referer,
    }
    try:
        async with session.get(image_url, headers=headers) as response:
            if response.status >= 400:
                return None

            image_bytes = await response.read()
            if not image_bytes:
                return None

            response_content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
            guessed_content_type, _ = mimetypes.guess_type(image_url)
            content_type = (
                _sniff_supported_content_type(image_bytes)
                or _normalize_content_type(response_content_type)
                or _normalize_content_type(guessed_content_type)
            )
            if content_type not in _SUPPORTED_IMAGE_CONTENT_TYPES:
                return None

            encoded = base64.b64encode(image_bytes).decode("ascii")
            return f"data:{content_type};base64,{encoded}"
    except Exception:
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


def _build_vlm_prompt(page: ExtractedPage) -> str:
    heading = f"# {page.title}"
    body = page.markdown.removeprefix(heading).strip() if page.title else page.markdown.strip()
    context = body[:4000]
    instructions = (
        "이미지에 보이는 상품 정보만 한국어 마크다운으로 보강하세요. "
        "가격, 할인, 프로모션, 옵션, 재질, 색상, 규격처럼 구매 판단에 중요한 정보만 간결하게 적고, "
        "DOM 본문에 이미 있는 문장은 반복하지 마세요."
    )
    if page.title:
        return f"제목: {page.title}\n\n기존 DOM 추출:\n{context}\n\n지시사항: {instructions}"
    return f"기존 DOM 추출:\n{context}\n\n지시사항: {instructions}"


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
