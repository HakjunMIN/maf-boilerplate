import pytest

from homestyle_ingestion.application.vlm import VlmEnrichmentService
from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.vlm import ImageCandidate, VlmExtraction, VlmExtractionError


@pytest.mark.asyncio
async def test_enrich_page_appends_vlm_markdown_after_existing_page_markdown() -> None:
    captured_calls: list[tuple[str, tuple[ImageCandidate, ...]]] = []

    async def extract_markdown(prompt: str, images: tuple[ImageCandidate, ...]) -> VlmExtraction:
        captured_calls.append((prompt, images))
        return VlmExtraction(
            markdown="## 이미지 설명\n\n패브릭 소파와 원목 테이블 조합입니다.",
            confidence_score=0.9,
        )

    service = VlmEnrichmentService(extract_markdown=extract_markdown)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="# 거실 컬렉션\n\n짧은 본문",
    )
    image_candidates = (
        ImageCandidate(width=320, role=None, aria_hidden=False),
    )

    enriched_page = await service.enrich_page(page, image_candidates)

    assert enriched_page == ExtractedPage(
        url=page.url,
        title=page.title,
        breadcrumb=page.breadcrumb,
        markdown=(
            "# 거실 컬렉션\n\n"
            "짧은 본문\n\n"
            "## 이미지 설명\n\n"
            "패브릭 소파와 원목 테이블 조합입니다."
        ),
        segments=(
            ExtractedSegment(
                segment_id=f"{page.url}#dom-1",
                markdown="# 거실 컬렉션\n\n짧은 본문",
            ),
            ExtractedSegment(
                segment_id=f"{page.url}#vlm-1",
                markdown="## 이미지 설명\n\n패브릭 소파와 원목 테이블 조합입니다.",
                source_kind="vlm",
                confidence_score=0.9,
                review_state="not_required",
                is_image_derived=True,
            ),
        ),
    )
    assert captured_calls == [
        ("거실 컬렉션\n\n짧은 본문", image_candidates),
    ]


@pytest.mark.asyncio
async def test_enrich_page_skips_vlm_when_no_meaningful_image_candidate_exists() -> None:
    called = False

    async def extract_markdown(_: str, __: tuple[ImageCandidate, ...]) -> VlmExtraction:
        nonlocal called
        called = True
        return VlmExtraction(markdown="## 이미지 설명", confidence_score=0.9)

    service = VlmEnrichmentService(extract_markdown=extract_markdown)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="# 거실 컬렉션\n\n짧은 본문",
    )

    enriched_page = await service.enrich_page(
        page,
        (
            ImageCandidate(width=80, role=None, aria_hidden=False),
            ImageCandidate(width=240, role="presentation", aria_hidden=False),
            ImageCandidate(width=320, role=None, aria_hidden=True),
        ),
    )

    assert enriched_page == page
    assert called is False


@pytest.mark.asyncio
async def test_enrich_page_returns_original_page_when_vlm_extraction_fails() -> None:
    async def extract_markdown(_: str, __: tuple[ImageCandidate, ...]) -> VlmExtraction:
        raise VlmExtractionError("vlm timeout")

    service = VlmEnrichmentService(extract_markdown=extract_markdown)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="짧은 본문",
    )

    enriched_page = await service.enrich_page(
        page,
        (ImageCandidate(width=320, role=None, aria_hidden=False),),
    )

    assert enriched_page == page


@pytest.mark.asyncio
async def test_enrich_page_passes_at_most_ten_meaningful_image_candidates_to_vlm() -> None:
    captured_images: list[tuple[ImageCandidate, ...]] = []

    async def extract_markdown(_: str, images: tuple[ImageCandidate, ...]) -> VlmExtraction:
        captured_images.append(images)
        return VlmExtraction(markdown="## 이미지 설명", confidence_score=0.9)

    service = VlmEnrichmentService(extract_markdown=extract_markdown)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="짧은 본문",
    )
    image_candidates = (
        ImageCandidate(width=80, role=None, aria_hidden=False),
        *(ImageCandidate(width=320 + index, role=None, aria_hidden=False) for index in range(12)),
    )

    await service.enrich_page(page, image_candidates)

    assert len(captured_images) == 1
    assert captured_images[0] == tuple(image for image in image_candidates if image.width >= 200)[:10]


@pytest.mark.asyncio
async def test_enrich_page_keeps_low_confidence_vlm_segment_out_of_page_markdown() -> None:
    async def extract_markdown(_: str, __: tuple[ImageCandidate, ...]) -> VlmExtraction:
        return VlmExtraction(
            markdown="## 이미지 설명\n\n검토가 필요한 이미지 유래 설명입니다.",
            confidence_score=0.4,
        )

    service = VlmEnrichmentService(extract_markdown=extract_markdown)
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("collection", "living-room"),
        markdown="# 거실 컬렉션\n\n짧은 본문",
    )

    enriched_page = await service.enrich_page(
        page,
        (ImageCandidate(width=320, role=None, aria_hidden=False),),
    )

    assert enriched_page.markdown == page.markdown
    assert enriched_page.segments == (
        ExtractedSegment(
            segment_id=f"{page.url}#dom-1",
            markdown="# 거실 컬렉션\n\n짧은 본문",
        ),
        ExtractedSegment(
            segment_id=f"{page.url}#vlm-1",
            markdown="## 이미지 설명\n\n검토가 필요한 이미지 유래 설명입니다.",
            source_kind="vlm",
            confidence_score=0.4,
            review_state="pending",
            is_image_derived=True,
        ),
    )
