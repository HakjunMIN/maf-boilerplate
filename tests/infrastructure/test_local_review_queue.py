from pathlib import Path

import pytest

from homestyle_ingestion.domain.review_queue import ReviewQueueItem
from homestyle_ingestion.infrastructure.review_queue import LocalReviewQueue, ReviewQueueItemNotFoundError


@pytest.mark.asyncio
async def test_local_review_queue_enqueues_and_lists_pending_items(tmp_path: Path) -> None:
    queue = LocalReviewQueue(root_directory=tmp_path)
    item = ReviewQueueItem(
        item_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
        page_url="https://homestyle.lge.co.kr/collection/living-room",
        segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
        markdown="## 이미지 설명\n\n검토가 필요한 설명입니다.",
        confidence_score=0.42,
        extraction_version="v2",
    )

    await queue.enqueue_items([item])

    assert await queue.list_pending() == [item]


@pytest.mark.asyncio
async def test_local_review_queue_marks_item_as_approved(tmp_path: Path) -> None:
    queue = LocalReviewQueue(root_directory=tmp_path)
    item = ReviewQueueItem(
        item_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
        page_url="https://homestyle.lge.co.kr/collection/living-room",
        segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
        markdown="## 이미지 설명\n\n검토가 필요한 설명입니다.",
        confidence_score=0.42,
        extraction_version="v2",
    )
    await queue.enqueue_items([item])

    await queue.mark_approved(item.item_id)

    assert await queue.list_pending() == []


@pytest.mark.asyncio
async def test_local_review_queue_raises_for_unknown_item_approval(tmp_path: Path) -> None:
    queue = LocalReviewQueue(root_directory=tmp_path)

    with pytest.raises(ReviewQueueItemNotFoundError, match="missing-item"):
        await queue.mark_approved("missing-item")
