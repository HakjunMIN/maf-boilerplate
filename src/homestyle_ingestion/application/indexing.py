from homestyle_ingestion.domain.extraction import ExtractedPage, ExtractedSegment
from homestyle_shared.domain.indexing import SectionDocument


class SectionSplitter:
    def split(
        self,
        page: ExtractedPage,
        locale: str,
        extraction_version: str = "v1",
    ) -> list[SectionDocument]:
        sections: list[SectionDocument] = []
        for segment in self._iter_indexable_segments(page):
            current_lines: list[str] = []
            current_heading = ""
            for line in segment.markdown.split("\n\n"):
                if line.startswith("## ") or line.startswith("### "):
                    if current_lines:
                        sections.append(
                            self._build_section(
                                page=page,
                                locale=locale,
                                segment=segment,
                                extraction_version=extraction_version,
                                section_number=len(sections) + 1,
                                section_heading=current_heading,
                                lines=current_lines,
                            )
                        )
                    current_lines = [line]
                    current_heading = line.removeprefix("## ").removeprefix("### ")
                    continue

                if current_lines:
                    current_lines.append(line)

            if current_lines:
                sections.append(
                    self._build_section(
                        page=page,
                        locale=locale,
                        segment=segment,
                        extraction_version=extraction_version,
                        section_number=len(sections) + 1,
                        section_heading=current_heading,
                        lines=current_lines,
                    )
                )

        return sections

    def _iter_indexable_segments(self, page: ExtractedPage) -> tuple[ExtractedSegment, ...]:
        if page.segments:
            return tuple(segment for segment in page.segments if segment.review_state != "pending")
        return (
            ExtractedSegment(
                segment_id=f"{page.url}#dom-1",
                markdown=page.markdown,
            ),
        )

    def _build_section(
        self,
        page: ExtractedPage,
        locale: str,
        segment: ExtractedSegment,
        extraction_version: str,
        section_number: int,
        section_heading: str,
        lines: list[str],
    ) -> SectionDocument:
        return SectionDocument(
            chunk_id=f"{page.url}#section-{section_number}",
            page_url=page.url,
            locale=locale,
            title=page.title,
            breadcrumb=page.breadcrumb,
            section_heading=section_heading,
            content="\n\n".join(lines),
            confidence_score=segment.confidence_score,
            is_image_derived=segment.is_image_derived,
            extraction_version=extraction_version,
            reviewer_approved=segment.review_state == "approved",
        )
