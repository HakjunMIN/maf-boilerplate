from homestyle_ingestion.domain.extraction import ExtractedPage
from homestyle_shared.domain.indexing import SectionDocument


class SectionSplitter:
    def split(self, page: ExtractedPage, locale: str) -> list[SectionDocument]:
        sections: list[SectionDocument] = []
        current_lines: list[str] = []
        current_heading = ""

        for line in page.markdown.split("\n\n"):
            if line.startswith("## ") or line.startswith("### "):
                if current_lines:
                    sections.append(
                        self._build_section(
                            page=page,
                            locale=locale,
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
                    section_number=len(sections) + 1,
                    section_heading=current_heading,
                    lines=current_lines,
                )
            )

        return sections

    def _build_section(
        self,
        page: ExtractedPage,
        locale: str,
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
        )
