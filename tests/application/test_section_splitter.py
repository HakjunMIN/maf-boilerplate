from homestyle_ingestion.application.indexing import SectionSplitter
from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_shared.domain.indexing import SectionDocument


def test_split_creates_sections_from_h2_and_h3_boundaries() -> None:
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("홈", "컬렉션", "거실"),
        markdown="\n\n".join(
            [
                "# 거실 컬렉션",
                "## 거실 제안",
                "밝은 톤의 거실 스타일링입니다.",
                "### 소파",
                "패브릭 소파를 중심으로 배치합니다.",
                "## 수납",
                "낮은 수납장을 활용합니다.",
            ]
        ),
    )

    sections = SectionSplitter().split(page=page, locale="ko")

    assert sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-1",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("홈", "컬렉션", "거실"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
        ),
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-2",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("홈", "컬렉션", "거실"),
            section_heading="소파",
            content="### 소파\n\n패브릭 소파를 중심으로 배치합니다.",
        ),
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-3",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("홈", "컬렉션", "거실"),
            section_heading="수납",
            content="## 수납\n\n낮은 수납장을 활용합니다.",
        ),
    ]


def test_split_preserves_segment_provenance_and_skips_pending_review_segments() -> None:
    page = ExtractedPage(
        url="https://homestyle.lge.co.kr/collection/living-room",
        title="거실 컬렉션",
        breadcrumb=("홈", "컬렉션", "거실"),
        markdown="# 거실 컬렉션\n\n## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
        segments=(
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#dom-1",
                markdown="## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
            ),
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-1",
                markdown="## 이미지 설명\n\n패브릭 소파 조합입니다.",
                source_kind="vlm",
                confidence_score=0.88,
                review_state="approved",
                is_image_derived=True,
            ),
            ExtractedSegment(
                segment_id="https://homestyle.lge.co.kr/collection/living-room#vlm-2",
                markdown="## 보류 설명\n\n검토 대기 중인 설명입니다.",
                source_kind="vlm",
                confidence_score=0.4,
                review_state="pending",
                is_image_derived=True,
            ),
        ),
    )

    sections = SectionSplitter().split(page=page, locale="ko", extraction_version="v2")

    assert sections == [
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-1",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("홈", "컬렉션", "거실"),
            section_heading="거실 제안",
            content="## 거실 제안\n\n밝은 톤의 거실 스타일링입니다.",
            confidence_score=1.0,
            is_image_derived=False,
            extraction_version="v2",
            reviewer_approved=False,
        ),
        SectionDocument(
            chunk_id="https://homestyle.lge.co.kr/collection/living-room#section-2",
            page_url=page.url,
            locale="ko",
            title="거실 컬렉션",
            breadcrumb=("홈", "컬렉션", "거실"),
            section_heading="이미지 설명",
            content="## 이미지 설명\n\n패브릭 소파 조합입니다.",
            confidence_score=0.88,
            is_image_derived=True,
            extraction_version="v2",
            reviewer_approved=True,
        ),
    ]
