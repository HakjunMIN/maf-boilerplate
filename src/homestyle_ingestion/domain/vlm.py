from dataclasses import dataclass


class VlmExtractionError(Exception):
    pass


@dataclass(frozen=True)
class ImageCandidate:
    width: int
    role: str | None
    aria_hidden: bool


@dataclass(frozen=True)
class ExtractedBlock:
    text: str
    images: tuple[ImageCandidate, ...]
