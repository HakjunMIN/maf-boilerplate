from collections.abc import Awaitable, Callable

from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_ingestion.domain.review_queue import ReviewQueueItem

EnqueueItems = Callable[[list[ReviewQueueItem]], Awaitable[None]]
MarkApproved = Callable[[str], Awaitable[None]]
MarkSegmentReviewed = Callable[[str, str], Awaitable[None]]


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


class ReviewQueueApprovalService:
    def __init__(
        self,
        *,
        mark_approved: MarkApproved,
        mark_segment_reviewed: MarkSegmentReviewed,
    ) -> None:
        self._mark_approved = mark_approved
        self._mark_segment_reviewed = mark_segment_reviewed

    async def approve(self, item: ReviewQueueItem) -> None:
        await self._mark_approved(item.item_id)
        await self._mark_segment_reviewed(item.page_url, item.segment_id)
