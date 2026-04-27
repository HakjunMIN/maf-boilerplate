from bs4 import BeautifulSoup, Tag
from urllib.parse import urlparse

from homestyle_ingestion.domain.extraction import ExtractedPage

_CONTENT_SELECTORS = ("main", "article", '[role="main"]')
_BOILERPLATE_SELECTORS = ("nav", "footer", "header", ".cookie-banner")
_BLOCK_TAGS = {"h1", "h2", "h3", "p"}
_BREADCRUMB_SELECTORS = ('nav[aria-label="breadcrumb"]', '[class*="breadcrumb"]')


class DomExtractionService:
    def extract(self, url: str, html: str) -> ExtractedPage:
        soup = BeautifulSoup(html, "lxml")
        breadcrumb = self._extract_breadcrumb(soup, url)
        for selector in _BOILERPLATE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        content_root = self._find_content_root(soup)
        if content_root is None:
            return ExtractedPage(url=url, title="", breadcrumb=(), markdown="")

        blocks: list[str] = []
        title = ""
        for element in content_root.descendants:
            if not isinstance(element, Tag) or element.name not in _BLOCK_TAGS:
                continue

            text = element.get_text(" ", strip=True)
            if not text:
                continue

            if element.name == "h1":
                title = title or text
                blocks.append(f"# {text}")
            elif element.name == "h2":
                blocks.append(f"## {text}")
            else:
                blocks.append(text)

        return ExtractedPage(
            url=url,
            title=title,
            breadcrumb=breadcrumb,
            markdown="\n\n".join(blocks),
        )

    def _find_content_root(self, soup: BeautifulSoup) -> Tag | None:
        for selector in _CONTENT_SELECTORS:
            content_root = soup.select_one(selector)
            if isinstance(content_root, Tag):
                return content_root
        return None

    def _extract_breadcrumb(self, soup: BeautifulSoup, url: str) -> tuple[str, ...]:
        for selector in _BREADCRUMB_SELECTORS:
            breadcrumb_root = soup.select_one(selector)
            if not isinstance(breadcrumb_root, Tag):
                continue

            items = tuple(
                text
                for text in (
                    element.get_text(" ", strip=True)
                    for element in breadcrumb_root.select("a, span, li")
                )
                if text
            )
            if items:
                return items

        path_segments = [segment for segment in urlparse(url).path.split("/") if segment]
        if len(path_segments) <= 1:
            return ()
        return tuple(path_segments)
