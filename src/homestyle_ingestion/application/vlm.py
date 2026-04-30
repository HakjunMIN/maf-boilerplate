from collections.abc import Awaitable, Callable

from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_ingestion.domain.vlm import (
    ExtractedBlock,
    ImageCandidate,
    VlmExtraction,
    VlmExtractionError,
)

ExtractMarkdown = Callable[[str, tuple[ImageCandidate, ...]], Awaitable[VlmExtraction]]


class VlmTriggerPolicy:
    def should_extract(self, block: ExtractedBlock) -> bool:
        if len(block.text) >= 50:
            return False

        return bool(self.meaningful_images(block.images))

    def meaningful_images(self, images: tuple[ImageCandidate, ...]) -> tuple[ImageCandidate, ...]:
        return tuple(image for image in images if self._is_meaningful_image(image))

    def _is_meaningful_image(self, image: ImageCandidate) -> bool:
        return (
            image.width >= 200
            and image.role != "presentation"
            and image.aria_hidden is False
        )


class VlmEnrichmentService:
    def __init__(
        self,
        *,
        extract_markdown: ExtractMarkdown,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._extract_markdown = extract_markdown
        self._trigger_policy = VlmTriggerPolicy()
        self._confidence_threshold = confidence_threshold

    async def enrich_page(
        self,
        page: ExtractedPage,
        image_candidates: tuple[ImageCandidate, ...],
    ) -> ExtractedPage:
        meaningful_images = self._trigger_policy.meaningful_images(image_candidates)
        if not self._trigger_policy.should_extract(
            ExtractedBlock(text=page.markdown, images=meaningful_images)
        ):
            return page
        try:
            extraction = await self._extract_markdown(
                self._build_prompt(page),
                meaningful_images[:10],
            )
        except VlmExtractionError:
            return page
        segments = self._base_segments(page)
        vlm_segment = ExtractedSegment(
            segment_id=f"{page.url}#vlm-{len([segment for segment in segments if segment.source_kind == 'vlm']) + 1}",
            markdown=extraction.markdown,
            source_kind="vlm",
            confidence_score=extraction.confidence_score,
            review_state=(
                "pending"
                if extraction.confidence_score < self._confidence_threshold
                else "not_required"
            ),
            is_image_derived=True,
        )
        if extraction.confidence_score < self._confidence_threshold:
            return ExtractedPage(
                url=page.url,
                title=page.title,
                breadcrumb=page.breadcrumb,
                markdown=page.markdown,
                segments=(*segments, vlm_segment),
            )
        return ExtractedPage(
            url=page.url,
            title=page.title,
            breadcrumb=page.breadcrumb,
            markdown=f"{page.markdown}\n\n{extraction.markdown}",
            segments=(*segments, vlm_segment),
        )

    def _build_prompt(self, page: ExtractedPage) -> str:
        heading = f"# {page.title}"
        body = page.markdown.removeprefix(heading).strip() if page.title else page.markdown.strip()
        return f"{page.title}\n\n{body}".strip() if page.title else body

    def _base_segments(self, page: ExtractedPage) -> tuple[ExtractedSegment, ...]:
        if page.segments:
            return page.segments
        return (
            ExtractedSegment(
                segment_id=f"{page.url}#dom-1",
                markdown=page.markdown,
            ),
        )
