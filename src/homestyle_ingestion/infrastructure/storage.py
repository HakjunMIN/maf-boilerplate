import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.fetch import FetchMetadata


class PageStoreNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class StoredPage:
    page: ExtractedPage
    metadata: FetchMetadata
    extraction_version: str


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
            metadata=FetchMetadata(
                url=metadata_payload["url"],
                etag=metadata_payload["etag"],
                last_modified=metadata_payload["last_modified"],
                content_hash=metadata_payload["content_hash"],
                fetch_failed=metadata_payload["fetch_failed"],
            ),
            extraction_version=str(payload["extraction_version"]),
        )

    def _storage_path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self._root_directory / f"{key}.json"
