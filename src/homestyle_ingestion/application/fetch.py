from collections.abc import Awaitable, Callable
import hashlib

from homestyle_ingestion.domain.discovery import DiscoveredUrl
from homestyle_ingestion.domain.fetch import (
    FetchExecutionError,
    FetchMetadata,
    FetchResponse,
    FetchResult,
)

FetchPage = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]


class ConditionalFetchService:
    def __init__(self, fetch_page: FetchPage) -> None:
        self._fetch_page = fetch_page

    async def fetch(
        self,
        discovered_url: DiscoveredUrl,
        previous_metadata: FetchMetadata,
    ) -> FetchResult:
        headers = self._build_headers(previous_metadata)
        try:
            response = await self._fetch_page(discovered_url.url, headers)
        except FetchExecutionError:
            return FetchResult(
                url=discovered_url.url,
                status="failed",
                body=None,
                metadata=self._metadata_with_fetch_failed(previous_metadata, fetch_failed=True),
            )

        if response.status_code == 304:
            return FetchResult(
                url=discovered_url.url,
                status="unchanged",
                body=None,
                metadata=self._metadata_with_fetch_failed(previous_metadata, fetch_failed=False),
            )

        content_hash = previous_metadata.content_hash
        if response.body is not None and response.etag is None and response.last_modified is None:
            content_hash = self._hash_content(response.body)
            if content_hash == previous_metadata.content_hash:
                return FetchResult(
                    url=discovered_url.url,
                    status="unchanged",
                    body=None,
                    metadata=self._metadata_with_fetch_failed(previous_metadata, fetch_failed=False),
                )

        return FetchResult(
            url=discovered_url.url,
            status="changed",
            body=response.body,
            metadata=FetchMetadata(
                url=discovered_url.url,
                etag=response.etag,
                last_modified=response.last_modified,
                content_hash=content_hash,
                fetch_failed=False,
            ),
        )

    def _build_headers(self, previous_metadata: FetchMetadata) -> dict[str, str]:
        headers: dict[str, str] = {}
        if previous_metadata.etag:
            headers["If-None-Match"] = previous_metadata.etag
        if previous_metadata.last_modified:
            headers["If-Modified-Since"] = previous_metadata.last_modified
        return headers

    def _hash_content(self, body: str) -> str:
        normalized_body = " ".join(body.split())
        return hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()

    def _metadata_with_fetch_failed(
        self,
        metadata: FetchMetadata,
        *,
        fetch_failed: bool,
    ) -> FetchMetadata:
        return FetchMetadata(
            url=metadata.url,
            etag=metadata.etag,
            last_modified=metadata.last_modified,
            content_hash=metadata.content_hash,
            fetch_failed=fetch_failed,
        )
