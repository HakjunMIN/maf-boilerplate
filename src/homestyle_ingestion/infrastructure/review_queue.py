import json
from pathlib import Path

from homestyle_ingestion.domain.review_queue import ReviewQueueItem


class ReviewQueueItemNotFoundError(Exception):
    pass


class LocalReviewQueue:
    def __init__(self, *, root_directory: Path) -> None:
        self._root_directory = root_directory

    async def enqueue_items(self, items: list[ReviewQueueItem]) -> None:
        payload = self._load_payload()
        items_by_id = {item["item_id"]: item for item in payload}
        for item in items:
            items_by_id[item.item_id] = {
                "item_id": item.item_id,
                "page_url": item.page_url,
                "segment_id": item.segment_id,
                "markdown": item.markdown,
                "confidence_score": item.confidence_score,
                "extraction_version": item.extraction_version,
                "status": item.status,
            }
        self._write_payload(list(items_by_id.values()))

    async def list_pending(self) -> list[ReviewQueueItem]:
        return [
            self._build_item(item)
            for item in self._load_payload()
            if item["status"] == "pending"
        ]

    async def mark_approved(self, item_id: str) -> None:
        payload = self._load_payload()
        updated = False
        for item in payload:
            if item["item_id"] == item_id:
                item["status"] = "approved"
                updated = True
                break
        if not updated:
            raise ReviewQueueItemNotFoundError(item_id)
        self._write_payload(payload)

    def _build_item(self, payload: dict[str, object]) -> ReviewQueueItem:
        return ReviewQueueItem(
            item_id=str(payload["item_id"]),
            page_url=str(payload["page_url"]),
            segment_id=str(payload["segment_id"]),
            markdown=str(payload["markdown"]),
            confidence_score=_normalize_float(payload["confidence_score"]),
            extraction_version=str(payload["extraction_version"]),
            status=str(payload["status"]),
        )

    def _queue_path(self) -> Path:
        return self._root_directory / "review-queue.json"

    def _load_payload(self) -> list[dict[str, object]]:
        queue_path = self._queue_path()
        if not queue_path.exists():
            return []
        return list(json.loads(queue_path.read_text(encoding="utf-8")))

    def _write_payload(self, payload: list[dict[str, object]]) -> None:
        self._root_directory.mkdir(parents=True, exist_ok=True)
        self._queue_path().write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


def _normalize_float(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return float(str(value))
