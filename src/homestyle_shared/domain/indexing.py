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
    confidence_score: float = 1.0
    is_image_derived: bool = False
    extraction_version: str = "v1"
    reviewer_approved: bool = False
