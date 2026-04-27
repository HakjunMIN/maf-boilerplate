from collections.abc import Awaitable, Callable

from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_ingestion.domain.vlm import ExtractedBlock, ImageCandidate, VlmExtractionError

ExtractMarkdown = Callable[[str, tuple[ImageCandidate, ...]], Awaitable[str]]


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
    def __init__(self, *, extract_markdown: ExtractMarkdown) -> None:
        self._extract_markdown = extract_markdown
        self._trigger_policy = VlmTriggerPolicy()

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
            additional_markdown = await self._extract_markdown(
                self._build_prompt(page),
                meaningful_images[:10],
            )
        except VlmExtractionError:
            return page
        return ExtractedPage(
            url=page.url,
            title=page.title,
            breadcrumb=page.breadcrumb,
            markdown=f"{page.markdown}\n\n{additional_markdown}",
        )

    def _build_prompt(self, page: ExtractedPage) -> str:
        heading = f"# {page.title}"
        body = page.markdown.removeprefix(heading).strip() if page.title else page.markdown.strip()
        return f"{page.title}\n\n{body}".strip() if page.title else body
