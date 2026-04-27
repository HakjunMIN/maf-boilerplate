import pytest

from homestyle_ingestion.application.indexing import SectionSplitter
from homestyle_ingestion.application.review_queue import ReviewQueueApprovalService, ReviewQueueService
from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.fetch import FetchMetadata
from homestyle_ingestion.infrastructure.review_queue import LocalReviewQueue
from homestyle_ingestion.infrastructure.storage import LocalPageStore
from homestyle_shared.domain.indexing import SectionDocument


@pytest.mark.asyncio
async def test_low_confidence_vlm_segment_stays_unindexed_until_review_approval(tmp_path) -> None:
    page_store = LocalPageStore(root_directory=tmp_path / "pages")
    review_queue = LocalReviewQueue(root_directory=tmp_path / "queue")
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="# 거실 컬렉션\n\n## 거실 제안\n\n짧은 본문",
        segments=(
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#dom-1",
                markdown="## 거실 제안\n\n짧은 본문",
            ),
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
                markdown="## 이미지 설명\n\n검토가 필요한 이미지 설명입니다.",
                source_kind="vlm",
                confidence_score=0.42,
                review_state="pending",
                is_image_derived=True,
            ),
        ),
    )
    metadata = FetchMetadata(
        url=page.url,
        etag='"etag-1"',
        last_modified="Mon, 21 Apr 2026 00:00:00 GMT",
        content_hash="hash-1",
    )
    await page_store.save_page(page, metadata, "v2")
    await ReviewQueueService(enqueue_items=review_queue.enqueue_items).enqueue_pending_segments(
        page=page,
        extraction_version="v2",
    )

    pending_sections = SectionSplitter().split(page=page, locale="ko", extraction_version="v2")
    pending_items = await review_queue.list_pending()

    assert pending_sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-1",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n짧은 본문",
            extraction_version="v2",
        )
    ]
    assert len(pending_items) == 1

    await ReviewQueueApprovalService(
        mark_approved=review_queue.mark_approved,
        mark_segment_reviewed=page_store.mark_segment_reviewed,
    ).approve(pending_items[0])

    approved_page = (await page_store.load_page(page.url)).page
    approved_sections = SectionSplitter().split(
        page=approved_page,
        locale="ko",
        extraction_version="v2",
    )

    assert approved_sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-1",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n짧은 본문",
            extraction_version="v2",
        ),
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-2",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("collection", "living-room"),
            section_heading="이미지 설명",
            content="## 이미지 설명\n\n검토가 필요한 이미지 설명입니다.",
            confidence_score=0.42,
            is_image_derived=True,
            extraction_version="v2",
            reviewer_approved=True,
        ),
    ]
