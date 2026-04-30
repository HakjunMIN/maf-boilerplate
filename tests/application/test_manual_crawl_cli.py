import pytest

from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_ingestion.domain.vlm import ImageCandidate
from homestyle_ingestion.manual_crawl_cli import (
    _build_vlm_prompt,
    _coerce_width,
    _download_image_as_data_url,
    _extract_image_candidates_from_html,
    _is_content_policy_violation,
    _report_progress,
    _resolve_vlm_config,
)


def test_resolve_vlm_config_requires_endpoint_and_deployment(monkeypatch) -> None:
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_VISION_DEPLOYMENT", raising=False)

    assert _resolve_vlm_config() is None

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_VISION_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-07-01-preview")

    assert _resolve_vlm_config() == (
        "https://example.openai.azure.com",
        "gpt-4.1-mini",
        "2025-07-01-preview",
    )


def test_extract_image_candidates_from_html_collects_http_sources_and_metadata() -> None:
    html = """
        <main>
          <img src="/images/product.jpg" width="320px" />
          <img data-src="https://cdn.example.com/hero.webp" width="640" role="presentation" />
          <img src="data:image/png;base64,abcd" width="200" />
          <img data-original="/images/promo.png" aria-hidden="true" />
        </main>
    """

    candidates, image_urls = _extract_image_candidates_from_html(
        "https://homestyle.lge.co.kr/item?productId=G123",
        html,
    )

    assert candidates == (
        ImageCandidate(width=320, role=None, aria_hidden=False),
        ImageCandidate(width=640, role="presentation", aria_hidden=False),
        ImageCandidate(width=400, role=None, aria_hidden=True),
    )
    assert image_urls == (
        "https://homestyle.lge.co.kr/images/product.jpg",
        "https://cdn.example.com/hero.webp",
        "https://homestyle.lge.co.kr/images/promo.png",
    )


def test_build_vlm_prompt_includes_existing_dom_context() -> None:
    prompt = _build_vlm_prompt(
        ExtractedPage(
            url="https://homestyle.lge.co.kr/item?productId=G123",
            title="오브제컬렉션 냉장고",
            breadcrumb=("item",),
            markdown="# 오브제컬렉션 냉장고\n\n3,290,000원\n\n카드 결제 시 7% 할인",
        )
    )

    assert "제목: 오브제컬렉션 냉장고" in prompt
    assert "기존 DOM 추출:" in prompt
    assert "3,290,000원" in prompt
    assert "DOM 본문에 이미 있는 문장은 반복하지 마세요." in prompt


def test_coerce_width_defaults_to_large_image_when_missing() -> None:
    assert _coerce_width(None) == 400


def test_report_progress_prints_current_position(capsys) -> None:
    _report_progress(2, 5, "https://homestyle.lge.co.kr/item?productId=G123")

    assert capsys.readouterr().out == (
        "[manual_crawl] [2/5] Processing https://homestyle.lge.co.kr/item?productId=G123\n"
    )


def test_is_content_policy_violation_matches_code_and_message() -> None:
    class FakeError(Exception):
        def __init__(self, message: str, code: str | None = None) -> None:
            super().__init__(message)
            self.code = code

    assert _is_content_policy_violation(FakeError("blocked", code="content_policy_violation")) is True
    assert _is_content_policy_violation(FakeError("Content safety system blocked this image")) is True
    assert _is_content_policy_violation(FakeError("some other bad request")) is False


@pytest.mark.asyncio
async def test_download_image_as_data_url_normalizes_supported_types() -> None:
    class FakeResponse:
        def __init__(self) -> None:
            self.status = 200
            self.headers = {"Content-Type": "image/jpg"}

        async def __aenter__(self) -> "FakeResponse":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def read(self) -> bytes:
            return b"\xff\xd8\xff\xe0jpeg"

    class FakeSession:
        def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
            assert url == "https://cdn.example.com/product.jpg"
            assert headers["Referer"] == "https://homestyle.lge.co.kr/item?productId=G123"
            assert headers["User-Agent"] == "LGHomeStyleBot/1.0"
            return FakeResponse()

    data_url = await _download_image_as_data_url(
        FakeSession(),
        image_url="https://cdn.example.com/product.jpg",
        referer="https://homestyle.lge.co.kr/item?productId=G123",
        user_agent="LGHomeStyleBot/1.0",
    )

    assert data_url == "data:image/jpeg;base64,/9j/4GpwZWc="