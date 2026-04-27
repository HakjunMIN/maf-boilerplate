from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewQueueItem:
    item_id: str
    page_url: str
    segment_id: str
    markdown: str
    confidence_score: float
    extraction_version: str
    status: str = "pending"
