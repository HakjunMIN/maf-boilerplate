from dataclasses import dataclass


@dataclass(frozen=True)
class SectionDocument:
    chunk_id: str
    page_url: str
    locale: str
    title: str
    breadcrumb: tuple[str, ...]
    content: str
    section_heading: str = ""
    product_id: str | None = None
    product_name: str | None = None
    confidence_score: float = 1.0
    is_image_derived: bool = False
    extraction_version: str = "v1"
    reviewer_approved: bool = False
