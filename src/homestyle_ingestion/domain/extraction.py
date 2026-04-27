from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedPage:
    url: str
    title: str
    breadcrumb: tuple[str, ...]
    markdown: str
