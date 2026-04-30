import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.fetch import FetchMetadata


class PageStoreNotFoundError(Exception):
    pass


class PageSegmentNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class StoredPage:
    page: ExtractedPage
    metadata: FetchMetadata
    extraction_version: str


@dataclass(frozen=True)
class StoredPageInventoryEntry:
    url: str
    metadata: FetchMetadata
    extraction_version: str
    is_deleted: bool = False
    deleted_at: str | None = None


class LocalPageStore:
    def __init__(self, *, root_directory: Path) -> None:
        self._root_directory = root_directory

    async def save_page(
        self,
        page: ExtractedPage,
        metadata: FetchMetadata,
        extraction_version: str,
    ) -> None:
        self._root_directory.mkdir(parents=True, exist_ok=True)
        storage_path = self._storage_path(page.url)
        storage_path.write_text(
            json.dumps(
                {
                    "page": {
                        "url": page.url,
                        "title": page.title,
                        "breadcrumb": list(page.breadcrumb),
                        "markdown": page.markdown,
                        "segments": [
                            {
                                "segment_id": segment.segment_id,
                                "markdown": segment.markdown,
                                "source_kind": segment.source_kind,
                                "confidence_score": segment.confidence_score,
                                "review_state": segment.review_state,
                                "is_image_derived": segment.is_image_derived,
                            }
                            for segment in page.segments
                        ],
                    },
                    "metadata": {
                        "url": metadata.url,
                        "etag": metadata.etag,
                        "last_modified": metadata.last_modified,
                        "content_hash": metadata.content_hash,
                        "fetch_failed": metadata.fetch_failed,
                    },
                    "extraction_version": extraction_version,
                    "is_deleted": False,
                    "deleted_at": None,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    async def load_page(self, url: str) -> StoredPage:
        storage_path = self._storage_path(url)
        if not storage_path.exists():
            raise PageStoreNotFoundError(url)
        payload = json.loads(storage_path.read_text(encoding="utf-8"))
        page_payload = payload["page"]
        metadata_payload = payload["metadata"]
        return StoredPage(
            page=ExtractedPage(
                url=page_payload["url"],
                title=page_payload["title"],
                breadcrumb=tuple(page_payload["breadcrumb"]),
                markdown=page_payload["markdown"],
                segments=tuple(
                    ExtractedSegment(
                        segment_id=str(segment["segment_id"]),
                        markdown=str(segment["markdown"]),
                        source_kind=str(segment["source_kind"]),
                        confidence_score=float(segment["confidence_score"]),
                        review_state=str(segment["review_state"]),
                        is_image_derived=bool(segment["is_image_derived"]),
                    )
                    for segment in page_payload.get("segments", [])
                ),
            ),
            metadata=self._metadata_from_payload(metadata_payload),
            extraction_version=str(payload["extraction_version"]),
        )

    async def list_pages(self) -> list[StoredPageInventoryEntry]:
        if not self._root_directory.exists():
            return []
        stored_pages: list[StoredPageInventoryEntry] = []
        for storage_path in sorted(self._root_directory.glob("*.json")):
            payload = json.loads(storage_path.read_text(encoding="utf-8"))
            metadata_payload = payload["metadata"]
            stored_pages.append(
                StoredPageInventoryEntry(
                    url=str(metadata_payload["url"]),
                    metadata=self._metadata_from_payload(metadata_payload),
                    extraction_version=str(payload["extraction_version"]),
                    is_deleted=bool(payload.get("is_deleted", False)),
                    deleted_at=payload.get("deleted_at"),
                )
            )
        return stored_pages

    async def mark_deleted(self, url: str, deleted_at: str) -> None:
        payload = self._load_payload(url)
        payload["is_deleted"] = True
        payload["deleted_at"] = deleted_at
        self._write_payload(url, payload)

    async def delete_page(self, url: str) -> None:
        storage_path = self._storage_path(url)
        if not storage_path.exists():
            raise PageStoreNotFoundError(url)
        storage_path.unlink()

    async def mark_segment_reviewed(self, url: str, segment_id: str) -> None:
        payload = self._load_payload(url)
        page_payload = payload.get("page")
        if not isinstance(page_payload, dict):
            raise PageStoreNotFoundError(url)

        segments = page_payload.get("segments", [])
        if not isinstance(segments, list):
            raise PageStoreNotFoundError(url)
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            if segment.get("segment_id") == segment_id:
                segment["review_state"] = "approved"
                self._write_payload(url, payload)
                return
        raise PageSegmentNotFoundError(segment_id)

    def _storage_path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self._root_directory / f"{key}.json"

    def _load_payload(self, url: str) -> dict[str, object]:
        storage_path = self._storage_path(url)
        if not storage_path.exists():
            raise PageStoreNotFoundError(url)
        return json.loads(storage_path.read_text(encoding="utf-8"))

    def _write_payload(self, url: str, payload: dict[str, object]) -> None:
        self._root_directory.mkdir(parents=True, exist_ok=True)
        self._storage_path(url).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def _metadata_from_payload(self, metadata_payload: dict[str, object]) -> FetchMetadata:
        return FetchMetadata(
            url=str(metadata_payload["url"]),
            etag=_normalize_optional_string(metadata_payload.get("etag")),
            last_modified=_normalize_optional_string(metadata_payload.get("last_modified")),
            content_hash=_normalize_optional_string(metadata_payload.get("content_hash")),
            fetch_failed=bool(metadata_payload["fetch_failed"]),
        )


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
