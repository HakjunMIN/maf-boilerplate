from collections.abc import Awaitable, Callable

from homestyle_shared.domain.indexing import SectionDocument

RetrieveSections = Callable[[str], Awaitable[list[SectionDocument]]]
GenerateGroundedBody = Callable[[str, list[SectionDocument]], Awaitable[str]]
DECLINE_MESSAGE = "현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다."


class GroundedQueryService:
    def __init__(
        self,
        retrieve_sections: RetrieveSections,
        generate_grounded_body: GenerateGroundedBody,
    ) -> None:
        self._retrieve_sections = retrieve_sections
        self._generate_grounded_body = generate_grounded_body

    async def answer(self, question: str) -> str:
        sections = await self._retrieve_sections(question)
        if not sections:
            return DECLINE_MESSAGE
        body = await self._generate_grounded_body(question, sections)
        citations = [
            f"[{index}] {section.page_url}" for index, section in enumerate(sections, start=1)
        ]
        return f"{body}\n\n" + "\n".join(citations)
