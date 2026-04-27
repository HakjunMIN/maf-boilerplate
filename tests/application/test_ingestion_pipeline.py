from pathlib import Path

import pytest

from homestyle_ingestion.application.ingestion import IngestionPipeline
from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_ingestion.domain.fetch import FetchMetadata, FetchResponse
from homestyle_ingestion.domain.vlm import ImageCandidate
from homestyle_shared.domain.indexing import SectionDocument


def write_config(tmp_path: Path) -> Path:
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


@pytest.mark.asyncio
async def test_ingestion_pipeline_discovers_fetches_extracts_splits_and_indexes(tmp_path: Path) -> None:
    text_responses = {
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
                <loc>https://homestyle.lge.co.kr/collection/living-room</loc>
              </url>
            </urlset>
        """,
    }
    indexed_sections: list[SectionDocument] = []

    async def fetch_text(url: str) -> str:
        return text_responses[url]

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == "https://homestyle.lge.co.kr/collection/living-room"
        assert headers == {}
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
            etag='"etag-1"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        )

    async def index_sections(sections: list[SectionDocument]) -> None:
        indexed_sections.extend(sections)

    pipeline = IngestionPipeline(
        fetch_text=fetch_text,
        fetch_page=fetch_page,
        index_sections=index_sections,
    )

    sections = await pipeline.run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
        previous_metadata_by_url={
            "https://homestyle.lge.co.kr/collection/living-room": FetchMetadata(
                url="https://homestyle.lge.co.kr/collection/living-room",
                etag=None,
                last_modified=None,
                content_hash=None,
            )
        },
    )

    assert sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-1",
            page_url="https://homestyle.lge.co.kr/collection/living-room",
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
        )
    ]
    assert indexed_sections == sections


@pytest.mark.asyncio
async def test_ingestion_pipeline_persists_extracted_page_markdown_with_fetch_metadata(
    tmp_path: Path,
) -> None:
    text_responses = {
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
                <loc>https://homestyle.lge.co.kr/collection/living-room</loc>
              </url>
            </urlset>
        """,
    }
    saved_pages: list[tuple[ExtractedPage, FetchMetadata, str]] = []

    async def fetch_text(url: str) -> str:
        return text_responses[url]

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == "https://homestyle.lge.co.kr/collection/living-room"
        assert headers == {}
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
            etag='"etag-1"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        )

    async def save_page(page: ExtractedPage, metadata: FetchMetadata, extraction_version: str) -> None:
        saved_pages.append((page, metadata, extraction_version))

    async def index_sections(_: list[SectionDocument]) -> None:
        return None

    await IngestionPipeline(
        fetch_text=fetch_text,
        fetch_page=fetch_page,
        save_page=save_page,
        extraction_version="v2",
        index_sections=index_sections,
    ).run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
        previous_metadata_by_url={
            "https://homestyle.lge.co.kr/collection/living-room": FetchMetadata(
                url="https://homestyle.lge.co.kr/collection/living-room",
                etag=None,
                last_modified=None,
                content_hash=None,
            )
        },
    )

    assert saved_pages == [
        (
            ExtractedPage(
                url="https://homestyle.lge.co.kr/collection/living-room",
                title="거실 컬렉션",
                breadcrumb=("collection", "living-room"),
                markdown="# 거실 컬렉션\n\n## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
            ),
            FetchMetadata(
                url="https://homestyle.lge.co.kr/collection/living-room",
                etag='"etag-1"',
                last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
                content_hash=None,
                fetch_failed=False,
            ),
            "v2",
        )
    ]


@pytest.mark.asyncio
async def test_ingestion_pipeline_uses_rendered_html_for_dom_extraction(tmp_path: Path) -> None:
    text_responses = {
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
                <loc>https://homestyle.lge.co.kr/collection/living-room</loc>
              </url>
            </urlset>
        """,
    }
    indexed_sections: list[SectionDocument] = []
    rendered_urls: list[str] = []

    async def fetch_text(url: str) -> str:
        return text_responses[url]

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == "https://homestyle.lge.co.kr/collection/living-room"
        assert headers == {}
        return FetchResponse(
            status_code=200,
            body="""
                <html>
                  <body>
                    <main>
                      <h1>원시 HTML 제목</h1>
                    </main>
                  </body>
                </html>
            """,
            etag='"etag-1"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        )

    async def render_page(url: str) -> str:
        rendered_urls.append(url)
        return """
            <html>
              <body>
                <main>
                  <h1>렌더된 거실 컬렉션</h1>
                  <section>
                    <h2>거실 제안</h2>
                    <p>렌더된 본문입니다.</p>
                  </section>
                </main>
              </body>
            </html>
        """

    async def index_sections(sections: list[SectionDocument]) -> None:
        indexed_sections.extend(sections)

    sections = await IngestionPipeline(
        fetch_text=fetch_text,
        fetch_page=fetch_page,
        render_page=render_page,
        index_sections=index_sections,
    ).run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
        previous_metadata_by_url={
            "https://homestyle.lge.co.kr/collection/living-room": FetchMetadata(
                url="https://homestyle.lge.co.kr/collection/living-room",
                etag=None,
                last_modified=None,
                content_hash=None,
            )
        },
    )

    assert rendered_urls == ["https://homestyle.lge.co.kr/collection/living-room"]
    assert sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-1",
            page_url="https://homestyle.lge.co.kr/collection/living-room",
            locale="ko",
            title="렌더된 거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n렌더된 본문입니다.",
        )
    ]
    assert indexed_sections == sections


@pytest.mark.asyncio
async def test_ingestion_pipeline_skips_page_when_renderer_fails_and_continues(
    tmp_path: Path,
) -> None:
    from homestyle_ingestion.domain.rendering import RenderPageError

    text_responses = {
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
                <loc>https://homestyle.lge.co.kr/collection/failing-page</loc>
              </url>
              <url>
                <loc>https://homestyle.lge.co.kr/collection/success-page</loc>
              </url>
            </urlset>
        """,
    }
    indexed_sections: list[SectionDocument] = []

    async def fetch_text(url: str) -> str:
        return text_responses[url]

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert headers == {}
        return FetchResponse(
            status_code=200,
            body=f"<html><body><main><h1>{url}</h1></main></body></html>",
            etag='"etag-1"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        )

    async def render_page(url: str) -> str:
        if url.endswith("/failing-page"):
            raise RenderPageError("render failed")
        return """
            <html>
              <body>
                <main>
                  <h1>성공한 페이지</h1>
                  <section>
                    <h2>거실 제안</h2>
                    <p>성공한 렌더 본문입니다.</p>
                  </section>
                </main>
              </body>
            </html>
        """

    async def index_sections(sections: list[SectionDocument]) -> None:
        indexed_sections.extend(sections)

    sections = await IngestionPipeline(
        fetch_text=fetch_text,
        fetch_page=fetch_page,
        render_page=render_page,
        index_sections=index_sections,
    ).run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
        previous_metadata_by_url={
            "https://homestyle.lge.co.kr/collection/failing-page": FetchMetadata(
                url="https://homestyle.lge.co.kr/collection/failing-page",
                etag=None,
                last_modified=None,
                content_hash=None,
            ),
            "https://homestyle.lge.co.kr/collection/success-page": FetchMetadata(
                url="https://homestyle.lge.co.kr/collection/success-page",
                etag=None,
                last_modified=None,
                content_hash=None,
            ),
        },
    )

    assert sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/success-page#section-1",
            page_url="https://homestyle.lge.co.kr/collection/success-page",
            locale="ko",
            title="성공한 페이지",
            breadcrumb=("collection", "success-page"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n성공한 렌더 본문입니다.",
        )
    ]
    assert indexed_sections == sections


@pytest.mark.asyncio
async def test_ingestion_pipeline_enriches_page_with_vlm_before_section_splitting(
    tmp_path: Path,
) -> None:
    text_responses = {
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
                <loc>https://homestyle.lge.co.kr/collection/living-room</loc>
              </url>
            </urlset>
        """,
    }
    indexed_sections: list[SectionDocument] = []
    captured_candidates: list[tuple[ImageCandidate, ...]] = []

    async def fetch_text(url: str) -> str:
        return text_responses[url]

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == "https://homestyle.lge.co.kr/collection/living-room"
        assert headers == {}
        return FetchResponse(
            status_code=200,
            body="""
                <html>
                  <body>
                    <main>
                      <h1>거실 컬렉션</h1>
                      <section>
                        <h2>거실 제안</h2>
                        <p>짧은 본문</p>
                      </section>
                    </main>
                  </body>
                </html>
            """,
            etag='"etag-1"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        )

    async def extract_image_candidates(_: str, __: str) -> tuple[ImageCandidate, ...]:
        return (ImageCandidate(width=320, role=None, aria_hidden=False),)

    async def enrich_page(page: ExtractedPage, image_candidates: tuple[ImageCandidate, ...]) -> ExtractedPage:
        captured_candidates.append(image_candidates)
        return ExtractedPage(
            url=page.url,
            title=page.title,
            breadcrumb=page.breadcrumb,
            markdown=f"{page.markdown}\n\n## 이미지 설명\n\n패브릭 소파 조합입니다.",
        )

    async def index_sections(sections: list[SectionDocument]) -> None:
        indexed_sections.extend(sections)

    sections = await IngestionPipeline(
        fetch_text=fetch_text,
        fetch_page=fetch_page,
        extract_image_candidates=extract_image_candidates,
        enrich_page=enrich_page,
        index_sections=index_sections,
    ).run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
        previous_metadata_by_url={
            "https://homestyle.lge.co.kr/collection/living-room": FetchMetadata(
                url="https://homestyle.lge.co.kr/collection/living-room",
                etag=None,
                last_modified=None,
                content_hash=None,
            )
        },
    )

    assert captured_candidates == [
        (ImageCandidate(width=320, role=None, aria_hidden=False),),
    ]
    assert sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-1",
            page_url="https://homestyle.lge.co.kr/collection/living-room",
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n짧은 본문",
        ),
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-2",
            page_url="https://homestyle.lge.co.kr/collection/living-room",
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="이미지 설명",
            content="## 이미지 설명\n\n패브릭 소파 조합입니다.",
        ),
    ]
    assert indexed_sections == sections
