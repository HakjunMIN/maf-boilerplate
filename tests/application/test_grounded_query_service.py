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
        "[1] https://homestyle.lge.co.kr/collection/living-room#section-1\n"
        "[2] https://homestyle.lge.co.kr/collection/living-room#section-2"
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
