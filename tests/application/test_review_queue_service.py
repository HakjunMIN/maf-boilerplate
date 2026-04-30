import pytest

from homestyle_ingestion.application.review_queue import ReviewQueueService
from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.review_queue import ReviewQueueItem


@pytest.mark.asyncio
async def test_review_queue_service_enqueues_only_pending_vlm_segments() -> None:
    captured_items: list[list[ReviewQueueItem]] = []

    async def enqueue_items(items: list[ReviewQueueItem]) -> None:
        captured_items.append(items)

    service = ReviewQueueService(enqueue_items=enqueue_items)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="# 거실 컬렉션\n\n짧은 본문",
        segments=(
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#dom-1",
                markdown="# 거실 컬렉션\n\n짧은 본문",
            ),
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
                markdown="## 이미지 설명\n\n검토가 필요한 설명입니다.",
                source_kind="vlm",
                confidence_score=0.42,
                review_state="pending",
                is_image_derived=True,
            ),
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-2",
                markdown="## 이미지 설명\n\n승인 불필요한 설명입니다.",
                source_kind="vlm",
                confidence_score=0.91,
                review_state="not_required",
                is_image_derived=True,
            ),
        ),
    )

    await service.enqueue_pending_segments(page=page, extraction_version="v2")

    assert captured_items == [
        [
            ReviewQueueItem(
                item_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
                page_url=page.url,
                segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
                markdown="## 이미지 설명\n\n검토가 필요한 설명입니다.",
                confidence_score=0.42,
                extraction_version="v2",
                status="pending",
            )
        ]
    ]
