import pytest

from homestyle_shared.domain.indexing import SectionDocument


@pytest.mark.asyncio
async def test_answer_returns_grounded_body_with_numbered_citations_from_retrieved_sections() -> None:
    from homestyle_agent.application.grounded_query import GroundedQueryService

    async def retrieve_sections(_: str) -> list[SectionDocument]:
        return [
            SectionDocument(
                chunk_id="chunk-1",
                page_url="https://homestyle.lge.co.kr/collection/living-room#section-1",
                locale="ko",
                title="거실 컬렉션",
                breadcrumb=("홈", "컬렉션", "거실"),
                section_heading="거실 제안",
                content="밝은 톤의 거실 스타일링입니다.",
            ),
            SectionDocument(
                chunk_id="chunk-2",
                page_url="https://homestyle.lge.co.kr/collection/living-room#section-2",
                locale="ko",
                title="거실 컬렉션",
                breadcrumb=("홈", "컬렉션", "거실"),
                section_heading="소파",
                content="패브릭 소파를 중심으로 배치합니다.",
            ),
        ]

    async def generate_grounded_body(_: str, __: list[SectionDocument]) -> str:
        return "밝은 톤의 거실 스타일링을 추천하며 패브릭 소파 중심 구성을 제안합니다."

    service = GroundedQueryService(
        retrieve_sections=retrieve_sections,
        generate_grounded_body=generate_grounded_body,
    )

    answer = await service.answer("거실 스타일링을 알려줘")

    assert answer == (
        "밝은 톤의 거실 스타일링을 추천하며 패브릭 소파 중심 구성을 제안합니다.\n\n"
        "[1] 거실 제안 - https://homestyle.lge.co.kr/collection/living-room#section-1\n"
        "[2] 소파 - https://homestyle.lge.co.kr/collection/living-room#section-2"
    )


@pytest.mark.asyncio
async def test_answer_declines_when_retrieval_returns_no_evidence() -> None:
    from homestyle_agent.application.grounded_query import GroundedQueryService

    async def retrieve_sections(_: str) -> list[SectionDocument]:
        return []

    async def generate_grounded_body(_: str, __: list[SectionDocument]) -> str:
        raise AssertionError("The model should not run when retrieval returns no evidence.")

    service = GroundedQueryService(
        retrieve_sections=retrieve_sections,
        generate_grounded_body=generate_grounded_body,
    )

    answer = await service.answer("침실 스타일링을 알려줘")

    assert answer == "현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다."


@pytest.mark.asyncio
async def test_answer_filters_unacceptable_evidence_before_generation() -> None:
    from homestyle_agent.application.grounded_query import GroundedQueryService

    async def retrieve_sections(_: str) -> list[SectionDocument]:
        return [
            SectionDocument(
                chunk_id="chunk-low-confidence",
                page_url="https://homestyle.lge.co.kr/item?productId=low",
                locale="ko",
                title="저신뢰 상품",
                breadcrumb=("홈",),
                section_heading="저신뢰 섹션",
                content="신뢰도가 낮은 근거입니다.",
                confidence_score=0.69,
            ),
            SectionDocument(
                chunk_id="chunk-en",
                page_url="https://homestyle.lge.co.kr/item?productId=en",
                locale="en",
                title="English product",
                breadcrumb=("Home",),
                section_heading="English section",
                content="English evidence.",
                confidence_score=0.95,
            ),
            SectionDocument(
                chunk_id="chunk-host",
                page_url="https://example.com/item?productId=bad",
                locale="ko",
                title="외부 상품",
                breadcrumb=("홈",),
                section_heading="외부 섹션",
                content="허용되지 않은 호스트 근거입니다.",
                confidence_score=0.95,
            ),
            SectionDocument(
                chunk_id="chunk-good",
                page_url="https://homestyle.lge.co.kr/item?productId=good",
                locale="ko",
                title="거실 상품",
                breadcrumb=("홈", "거실"),
                section_heading="거실 제안",
                content="허용된 근거입니다.",
                confidence_score=0.7,
            ),
        ]

    async def generate_grounded_body(
        _: str,
        sections: list[SectionDocument],
    ) -> str:
        assert [section.chunk_id for section in sections] == ["chunk-good"]
        return "허용된 근거만 사용했습니다."

    service = GroundedQueryService(
        retrieve_sections=retrieve_sections,
        generate_grounded_body=generate_grounded_body,
    )

    answer = await service.answer("거실 스타일링을 알려줘")

    assert answer == (
        "허용된 근거만 사용했습니다.\n\n"
        "[1] 거실 제안 - https://homestyle.lge.co.kr/item?productId=good"
    )


@pytest.mark.asyncio
async def test_answer_declines_when_all_retrieved_evidence_is_filtered_out() -> None:
    from homestyle_agent.application.grounded_query import GroundedQueryService

    async def retrieve_sections(_: str) -> list[SectionDocument]:
        return [
            SectionDocument(
                chunk_id="chunk-low-confidence",
                page_url="https://homestyle.lge.co.kr/item?productId=low",
                locale="ko",
                title="저신뢰 상품",
                breadcrumb=("홈",),
                section_heading="저신뢰 섹션",
                content="신뢰도가 낮은 근거입니다.",
                confidence_score=0.69,
            )
        ]

    async def generate_grounded_body(_: str, __: list[SectionDocument]) -> str:
        raise AssertionError("The model should not run when all evidence is filtered out.")

    service = GroundedQueryService(
        retrieve_sections=retrieve_sections,
        generate_grounded_body=generate_grounded_body,
    )

    answer = await service.answer("거실 스타일링을 알려줘")

    assert answer == "현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다."


@pytest.mark.asyncio
async def test_answer_deduplicates_citation_urls_and_removes_unsupported_body_urls() -> None:
    from homestyle_agent.application.grounded_query import GroundedQueryService

    async def retrieve_sections(_: str) -> list[SectionDocument]:
        return [
            SectionDocument(
                chunk_id="chunk-1",
                page_url="https://homestyle.lge.co.kr/item?productId=G25070000210",
                locale="ko",
                title="거실 상품",
                breadcrumb=("홈", "거실"),
                section_heading="거실 제안",
                content="첫 번째 근거입니다.",
                confidence_score=0.95,
            ),
            SectionDocument(
                chunk_id="chunk-2",
                page_url="https://homestyle.lge.co.kr/item?productId=G25070000210",
                locale="ko",
                title="거실 상품",
                breadcrumb=("홈", "거실"),
                section_heading="구매 정보",
                content="두 번째 근거입니다.",
                confidence_score=0.95,
            ),
        ]

    async def generate_grounded_body(_: str, __: list[SectionDocument]) -> str:
        return "근거 기반 답변입니다. https://unsupported.example/path"

    service = GroundedQueryService(
        retrieve_sections=retrieve_sections,
        generate_grounded_body=generate_grounded_body,
    )

    answer = await service.answer("거실 스타일링을 알려줘")

    assert answer == (
        "근거 기반 답변입니다.\n\n"
        "[1] 거실 제안 - https://homestyle.lge.co.kr/item?productId=G25070000210"
    )
