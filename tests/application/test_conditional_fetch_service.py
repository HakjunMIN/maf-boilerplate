import pytest

from homestyle_ingestion.application.fetch import ConditionalFetchService
from homestyle_ingestion.domain.discovery import DiscoveredUrl
from homestyle_ingestion.domain.fetch import (
    FetchExecutionError,
    FetchMetadata,
    FetchResponse,
    FetchResult,
)


@pytest.mark.asyncio
async def test_fetch_uses_conditional_headers_and_marks_304_as_unchanged() -> None:
    captured_request: dict[str, object] = {}

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        captured_request["url"] = url
        captured_request["headers"] = headers
        return FetchResponse(
            status_code=304,
            body=None,
            etag='"etag-123"',
            last_modified="Sun, 20 Apr 2026 00:00:00 GMT",
        )

    service = ConditionalFetchService(fetch_page=fetch_page)
    discovered_url = DiscoveredUrl(
        url="https://homestyle.lge.co.kr/shop?superCategoryId=2506000003",
        locale="ko",
        lastmod="2026-04-20",
        source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_product-list.xml",
    )
    previous_metadata = FetchMetadata(
        url=discovered_url.url,
        etag='"etag-123"',
        last_modified="Sun, 20 Apr 2026 00:00:00 GMT",
        content_hash=None,
    )

    result = await service.fetch(discovered_url=discovered_url, previous_metadata=previous_metadata)

    assert captured_request == {
        "url": "https://homestyle.lge.co.kr/shop?superCategoryId=2506000003",
        "headers": {
            "If-None-Match": '"etag-123"',
            "If-Modified-Since": "Sun, 20 Apr 2026 00:00:00 GMT",
        },
    }
    assert result == FetchResult(
        url=discovered_url.url,
        status="unchanged",
        body=None,
        metadata=previous_metadata,
    )


@pytest.mark.asyncio
async def test_fetch_marks_200_response_as_changed_and_refreshes_metadata() -> None:
    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == "https://homestyle.lge.co.kr/collection"
        assert headers == {"If-None-Match": '"old-etag"'}
        return FetchResponse(
            status_code=200,
            body="<html>fresh body</html>",
            etag='"new-etag"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        )

    service = ConditionalFetchService(fetch_page=fetch_page)
    discovered_url = DiscoveredUrl(
        url="https://homestyle.lge.co.kr/collection",
        locale="ko",
        lastmod="2026-04-21",
        source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
    )
    previous_metadata = FetchMetadata(
        url=discovered_url.url,
        etag='"old-etag"',
        last_modified=None,
        content_hash=None,
    )

    result = await service.fetch(discovered_url=discovered_url, previous_metadata=previous_metadata)

    assert result == FetchResult(
        url=discovered_url.url,
        status="changed",
        body="<html>fresh body</html>",
        metadata=FetchMetadata(
            url=discovered_url.url,
            etag='"new-etag"',
            last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
            content_hash=None,
        ),
    )


@pytest.mark.asyncio
async def test_fetch_uses_normalized_content_hash_when_response_has_no_validators() -> None:
    responses = iter(
        [
            FetchResponse(
                status_code=200,
                body="<main>same\ncontent</main>",
                etag=None,
                last_modified=None,
            ),
            FetchResponse(
                status_code=200,
                body="<main>new content</main>",
                etag=None,
                last_modified=None,
            ),
        ]
    )

    async def fetch_page(url: str, headers: dict[str, str]) -> FetchResponse:
        assert url == "https://homestyle.lge.co.kr/home"
        assert headers == {}
        return next(responses)

    service = ConditionalFetchService(fetch_page=fetch_page)
    discovered_url = DiscoveredUrl(
        url="https://homestyle.lge.co.kr/home",
        locale="ko",
        lastmod="2026-04-20",
        source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
    )
    previous_metadata = FetchMetadata(
        url=discovered_url.url,
        etag=None,
        last_modified=None,
        content_hash="f3831085157af65b6215158c337cfb66273576fac521d6ec1aeef104317ab0ef",
    )

    unchanged_result = await service.fetch(
        discovered_url=discovered_url,
        previous_metadata=previous_metadata,
    )
    changed_result = await service.fetch(
        discovered_url=discovered_url,
        previous_metadata=previous_metadata,
    )

    assert unchanged_result == FetchResult(
        url=discovered_url.url,
        status="unchanged",
        body=None,
        metadata=previous_metadata,
    )
    assert changed_result == FetchResult(
        url=discovered_url.url,
        status="changed",
        body="<main>new content</main>",
        metadata=FetchMetadata(
            url=discovered_url.url,
            etag=None,
            last_modified=None,
            content_hash="0f2c0e621410af9b67d6cb7f43c30ab5df7560d573fbe189bb93e049298bb559",
        ),
    )


@pytest.mark.asyncio
async def test_fetch_marks_fetch_failures_in_metadata_when_runtime_errors() -> None:
    async def fetch_page(_: str, __: dict[str, str]) -> FetchResponse:
        raise FetchExecutionError("Fetch failed after 3 attempts.")

    service = ConditionalFetchService(fetch_page=fetch_page)
    discovered_url = DiscoveredUrl(
        url="https://homestyle.lge.co.kr/home",
        locale="ko",
        lastmod="2026-04-20",
        source_sitemap_url="https://homestyle.lge.co.kr/sitemap/sitemap_collection.xml",
    )
    previous_metadata = FetchMetadata(
        url=discovered_url.url,
        etag='"etag-1"',
        last_modified="Sun, 20 Apr 2026 00:00:00 GMT",
        content_hash="existing-hash",
    )

    result = await service.fetch(discovered_url=discovered_url, previous_metadata=previous_metadata)

    assert result == FetchResult(
        url=discovered_url.url,
        status="failed",
        body=None,
        metadata=FetchMetadata(
            url=discovered_url.url,
            etag='"etag-1"',
            last_modified="Sun, 20 Apr 2026 00:00:00 GMT",
            content_hash="existing-hash",
            fetch_failed=True,
        ),
    )
