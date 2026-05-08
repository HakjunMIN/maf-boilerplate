from collections.abc import Awaitable, Callable
import re
from urllib.parse import urlparse

from homestyle_shared.domain.indexing import SectionDocument

RetrieveSections = Callable[[str], Awaitable[list[SectionDocument]]]
GenerateGroundedBody = Callable[[str, list[SectionDocument]], Awaitable[str]]
DECLINE_MESSAGE = "현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다."
_ALLOWED_SOURCE_HOST = "homestyle.lge.co.kr"
_MIN_CONFIDENCE_SCORE = 0.7
_VISIBLE_URL_PATTERN = re.compile(r"https?://\S+")


class GroundedQueryService:
    def __init__(
        self,
        retrieve_sections: RetrieveSections,
        generate_grounded_body: GenerateGroundedBody,
    ) -> None:
        self._retrieve_sections = retrieve_sections
        self._generate_grounded_body = generate_grounded_body

    async def answer(self, question: str) -> str:
        sections = _deduplicate_sections(_filter_acceptable_sections(await self._retrieve_sections(question)))
        if not sections:
            return DECLINE_MESSAGE
        body = _strip_visible_urls(await self._generate_grounded_body(question, sections))
        citations = [
            f"[{index}] {_citation_label(section)} - {section.page_url}"
            for index, section in enumerate(sections, start=1)
        ]
        return f"{body}\n\n" + "\n".join(citations)


def _filter_acceptable_sections(sections: list[SectionDocument]) -> list[SectionDocument]:
    return [section for section in sections if _is_acceptable_section(section)]


def _is_acceptable_section(section: SectionDocument) -> bool:
    return (
        section.locale == "ko"
        and section.confidence_score >= _MIN_CONFIDENCE_SCORE
        and urlparse(section.page_url).hostname == _ALLOWED_SOURCE_HOST
    )


def _deduplicate_sections(sections: list[SectionDocument]) -> list[SectionDocument]:
    seen_urls: set[str] = set()
    deduplicated: list[SectionDocument] = []
    for section in sections:
        if section.page_url in seen_urls:
            continue
        seen_urls.add(section.page_url)
        deduplicated.append(section)
    return deduplicated


def _citation_label(section: SectionDocument) -> str:
    if section.section_heading:
        return section.section_heading
    return section.title


def _strip_visible_urls(body: str) -> str:
    return _VISIBLE_URL_PATTERN.sub("", body).strip()
