from urllib.parse import parse_qs, urlparse

from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_shared.domain.indexing import SectionDocument


class SectionSplitter:
    def split(
        self,
        page: ExtractedPage,
        locale: str,
        extraction_version: str = "v1",
    ) -> list[SectionDocument]:
        segments = self._iter_indexable_segments(page)
        if not segments:
            return []

        product_id = self._extract_product_id(page.url)
        return [
            SectionDocument(
                chunk_id=page.url,
                page_url=page.url,
                locale=locale,
                title=page.title,
                breadcrumb=page.breadcrumb,
                content=page.markdown,
                product_id=product_id,
                product_name=page.title,
                confidence_score=min(segment.confidence_score for segment in segments),
                is_image_derived=any(segment.is_image_derived for segment in segments),
                extraction_version=extraction_version,
                reviewer_approved=any(segment.review_state == "approved" for segment in segments)
                and all(segment.review_state in {"approved", "not_required"} for segment in segments),
            )
        ]

    def _iter_indexable_segments(self, page: ExtractedPage) -> tuple[ExtractedSegment, ...]:
        if page.segments:
            return tuple(segment for segment in page.segments if segment.review_state != "pending")
        return (
            ExtractedSegment(
                segment_id=f"{page.url}#dom-1",
                markdown=page.markdown,
            ),
        )

    def _extract_product_id(self, page_url: str) -> str | None:
        query = parse_qs(urlparse(page_url).query)
        product_ids = query.get("productId")
        if not product_ids:
            return None
        product_id = product_ids[0].strip()
        return product_id or None
