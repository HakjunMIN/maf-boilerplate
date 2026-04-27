from collections.abc import Awaitable, Callable

from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_ingestion.domain.review_queue import ReviewQueueItem

EnqueueItems = Callable[[list[ReviewQueueItem]], Awaitable[None]]


class ReviewQueueService:
    def __init__(self, *, enqueue_items: EnqueueItems) -> None:
        self._enqueue_items = enqueue_items

    async def enqueue_pending_segments(
        self,
        *,
        page: ExtractedPage,
        extraction_version: str,
    ) -> None:
        items = [
            ReviewQueueItem(
                item_id=segment.segment_id,
                page_url=page.url,
                segment_id=segment.segment_id,
                markdown=segment.markdown,
                confidence_score=segment.confidence_score,
                extraction_version=extraction_version,
            )
            for segment in page.segments
            if segment.review_state == "pending"
        ]
        if items:
            await self._enqueue_items(items)
