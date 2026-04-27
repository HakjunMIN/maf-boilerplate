from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedSegment:
    segment_id: str
    markdown: str
    source_kind: str = "dom"
    confidence_score: float = 1.0
    review_state: str = "not_required"
    is_image_derived: bool = False


@dataclass(frozen=True)
class ExtractedPage:
    url: str
    title: str
    breadcrumb: tuple[str, ...]
    markdown: str
    segments: tuple[ExtractedSegment, ...] = ()
