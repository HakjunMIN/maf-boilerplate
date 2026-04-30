from pathlib import Path

import pytest

from homestyle_agent.application.grounded_query import GroundedQueryService
from homestyle_ingestion.application.ingestion import IngestionPipeline
from homestyle_ingestion.domain.fetch import FetchMetadata, FetchResponse
from homestyle_shared.domain.indexing import SectionDocument


def write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "discovery.toml"
    config_path.write_text(
        "\n".join(
            [
                "[discovery]",
                'locale = "ko"',
                'allowed_hosts = ["homestyle.lge.co.kr"]',
            ]
        ),
        encoding="utf-8",
    )
    return config_path


@pytest.mark.asyncio
async def test_smoke_path_ingests_sections_then_answers_from_retrieved_evidence(tmp_path: Path) -> None:
    text_responses = {
        "https://static-store.lge.co.kr/sitemap/sitemap.xml": """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap>
                                <loc>https://homestyle.lge.co.kr/sitemap/sitemap_product.xml</loc>
              </sitemap>
            </sitemapindex>
        """,
                "https://homestyle.lge.co.kr/sitemap/sitemap_product.xml": """
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url>
                                <loc>https://homestyle.lge.co.kr/item?productId=G25070000210</loc>
              </url>
            </urlset>
        """,
    }
    indexed_sections: list[SectionDocument] = []

    async def fetch_text(url: str) -> str:
        return text_responses[url]

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == "https://homestyle.lge.co.kr/item?productId=G25070000210"
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
        assert url == "https://homestyle.lge.co.kr/item?productId=G25070000210"
        return """
            <html>
              <body>
                <main>
                  <h1>렌더된 거실 컬렉션</h1>
                  <section>
                    <h2>거실 제안</h2>
                    <p>렌더된 본문 근거입니다.</p>
                  </section>
                </main>
              </body>
            </html>
        """

    async def index_sections(sections: list[SectionDocument]) -> None:
        indexed_sections.extend(sections)

    async def retrieve_sections(_: str) -> list[SectionDocument]:
        return indexed_sections

    async def generate_grounded_body(_: str, __: list[SectionDocument]) -> str:
        return "렌더된 본문 근거입니다."

    await IngestionPipeline(
        fetch_text=fetch_text,
        fetch_page=fetch_page,
        render_page=render_page,
        index_sections=index_sections,
    ).run(
        sitemap_index_url="https://static-store.lge.co.kr/sitemap/sitemap.xml",
        config_path=write_config(tmp_path),
        previous_metadata_by_url={
            "https://homestyle.lge.co.kr/item?productId=G25070000210": FetchMetadata(
                url="https://homestyle.lge.co.kr/item?productId=G25070000210",
                etag=None,
                last_modified=None,
                content_hash=None,
            )
        },
    )

    answer = await GroundedQueryService(
        retrieve_sections=retrieve_sections,
        generate_grounded_body=generate_grounded_body,
    ).answer("거실 스타일링을 알려줘")

    assert answer == (
        "렌더된 본문 근거입니다.\n\n"
        "[1] https://homestyle.lge.co.kr/item?productId=G25070000210"
    )
