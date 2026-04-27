from homestyle_ingestion.application.indexing import SectionSplitter
from homestyle_ingestion.domain.extraction import ExtractedPage
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
