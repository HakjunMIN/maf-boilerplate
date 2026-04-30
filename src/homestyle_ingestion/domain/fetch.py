from dataclasses import dataclass


class FetchExecutionError(Exception):
    """Raised when the fetch runtime exhausts retries."""


@dataclass(frozen=True)
class FetchMetadata:
    url: str
    etag: str | None
    last_modified: str | None
    content_hash: str | None
    fetch_failed: bool = False


@dataclass(frozen=True)
class FetchResponse:
    status_code: int
    body: str | None
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: str
    body: str | None
    metadata: FetchMetadata
