from dataclasses import dataclass


@dataclass(frozen=True)
class SectionDocument:
    chunk_id: str
    page_url: str
    locale: str
    title: str
    breadcrumb: tuple[str, ...]
    section_heading: str
    content: str
