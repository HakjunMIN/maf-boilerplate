import re

from crawl4ai import LXMLWebScrapingStrategy
from lxml import html as lhtml
from urllib.parse import urlparse

from homestyle_ingestion.domain.extraction import ExtractedPage

_CONTENT_ROOT_XPATHS = (
    "//main",
    "//article",
    '//*[@role="main"]',
)
_CRAWL4AI_EXCLUDED_TAGS = (
    "nav",
    "footer",
    "header",
    "aside",
    "script",
    "style",
    "noscript",
    "iframe",
)
_POST_CLEANUP_XPATHS = (
    '//*[contains(concat(" ", normalize-space(@class), " "), " cookie-banner ")]',
    '//*[contains(concat(" ", normalize-space(@class), " "), " toast ")]',
    '//*[contains(concat(" ", normalize-space(@class), " "), " modal ")]',
    '//*[@aria-hidden="true"]',
)
_BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "dt", "dd"}
_BREADCRUMB_XPATHS = (
    '//nav[@aria-label="breadcrumb"]',
    '//*[contains(@class, "breadcrumb")]',
)
_PROMOTION_SELECTORS = (
    '[class*="price"]',
    '[id*="price"]',
    '[class*="promo"]',
    '[id*="promo"]',
    '[class*="benefit"]',
    '[id*="benefit"]',
    '[class*="discount"]',
    '[id*="discount"]',
    '[class*="coupon"]',
    '[id*="coupon"]',
    '[class*="event"]',
    '[id*="event"]',
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_PRICE_PATTERN = re.compile(r"((₩|￦|KRW)\s?[\d,]+|[\d,]+\s?원)")
_PROMOTION_PATTERN = re.compile(r"(할인|혜택|쿠폰|이벤트|사은품|프로모션|특가|세일)")
_PROMOTION_TAGS = {"div", "span", "strong", "em"}


class DomExtractionService:
    def __init__(
        self,
        *,
        scraping_strategy: LXMLWebScrapingStrategy | None = None,
    ) -> None:
        self._scraping_strategy = scraping_strategy or LXMLWebScrapingStrategy()

    def extract(self, url: str, html: str) -> ExtractedPage:
        raw_root = self._parse_html(html)
        breadcrumb = self._extract_breadcrumb(raw_root, url)

        scraping_result = self._scraping_strategy.scrap(
            url=url,
            html=html,
            excluded_tags=list(_CRAWL4AI_EXCLUDED_TAGS),
            word_count_threshold=1,
        )
        cleaned_root = self._parse_html(
            scraping_result.cleaned_html if scraping_result.success and scraping_result.cleaned_html else html,
        )
        self._remove_post_cleanup_nodes(cleaned_root)

        content_root = self._find_content_root(cleaned_root)
        if content_root is None:
            return ExtractedPage(url=url, title="", breadcrumb=(), markdown="")

        blocks: list[str] = []
        seen_texts: set[str] = set()
        title = ""
        for element in content_root.iterdescendants():
            if not isinstance(element.tag, str):
                continue

            if element.tag in _BLOCK_TAGS:
                block = self._extract_block(element)
                if block is None:
                    continue
                title = self._capture_title(title, element, block)
                self._append_unique(blocks, seen_texts, block)
                continue

            if element.tag == "tr":
                table_row = self._extract_table_row(element)
                if table_row is not None:
                    self._append_unique(blocks, seen_texts, table_row)
                continue

            if element.tag in _PROMOTION_TAGS and self._is_promotional_element(element):
                promotion_text = self._normalize_text(element.text_content())
                if self._should_keep_text(promotion_text, minimum_length=4):
                    self._append_unique(blocks, seen_texts, promotion_text)

        return ExtractedPage(
            url=url,
            title=title,
            breadcrumb=breadcrumb,
            markdown="\n\n".join(blocks),
        )

    def _extract_block(self, element: lhtml.HtmlElement) -> str | None:
        text = self._normalize_text(element.text_content())
        if element.tag in {"h1", "h2", "h3", "h4"}:
            if not text:
                return None
        elif element.tag in {"p", "li", "dt", "dd"}:
            if not self._should_keep_text(text, minimum_length=4):
                return None
        elif not self._should_keep_text(text):
            return None

        if element.tag == "h1":
            return f"# {text}"
        if element.tag == "h2":
            return f"## {text}"
        if element.tag == "h3":
            return f"### {text}"
        if element.tag == "h4":
            return f"#### {text}"
        if element.tag == "li":
            return f"- {text}"
        return text

    def _extract_table_row(self, element: lhtml.HtmlElement) -> str | None:
        cells = [
            self._normalize_text(cell.text_content())
            for cell in element.xpath("./th | ./td")
        ]
        meaningful_cells = [cell for cell in cells if self._should_keep_text(cell, minimum_length=2)]
        if not meaningful_cells:
            return None
        return " | ".join(meaningful_cells)

    def _capture_title(self, current_title: str, element: lhtml.HtmlElement, block: str) -> str:
        if current_title or element.tag != "h1":
            return current_title
        return block.removeprefix("# ").strip()

    def _append_unique(self, blocks: list[str], seen_texts: set[str], block: str) -> None:
        normalized_block = self._normalize_text(block)
        dedupe_key = normalized_block.removeprefix("# ").removeprefix("## ").removeprefix("### ").removeprefix("#### ").removeprefix("- ").strip()
        if dedupe_key in seen_texts:
            return
        seen_texts.add(dedupe_key)
        blocks.append(normalized_block)

    def _normalize_text(self, text: str) -> str:
        return _WHITESPACE_PATTERN.sub(" ", text).strip()

    def _should_keep_text(self, text: str, *, minimum_length: int = 20) -> bool:
        if not text:
            return False
        if len(text) >= minimum_length:
            return True
        return bool(_PRICE_PATTERN.search(text) or _PROMOTION_PATTERN.search(text))

    def _is_promotional_element(self, element: lhtml.HtmlElement) -> bool:
        classes = str(element.get("class", ""))
        element_id = str(element.get("id", ""))
        identifier = f"{classes} {element_id}".lower()
        return any(token in identifier for token in ("price", "promo", "benefit", "discount", "coupon", "event"))

    def _find_content_root(self, root: lhtml.HtmlElement) -> lhtml.HtmlElement | None:
        for xpath in _CONTENT_ROOT_XPATHS:
            content_roots = root.xpath(xpath)
            if content_roots:
                return content_roots[0]
        return None

    def _extract_breadcrumb(self, root: lhtml.HtmlElement, url: str) -> tuple[str, ...]:
        for xpath in _BREADCRUMB_XPATHS:
            breadcrumb_roots = root.xpath(xpath)
            if not breadcrumb_roots:
                continue
            breadcrumb_root = breadcrumb_roots[0]

            items = tuple(
                text
                for text in (
                    self._normalize_text(element.text_content())
                    for element in breadcrumb_root.xpath(".//a | .//span | .//li")
                )
                if text
            )
            if items:
                return items

        path_segments = [segment for segment in urlparse(url).path.split("/") if segment]
        if len(path_segments) <= 1:
            return ()
        return tuple(path_segments)

    def _parse_html(self, html: str) -> lhtml.HtmlElement:
        return lhtml.document_fromstring(html)

    def _remove_post_cleanup_nodes(self, root: lhtml.HtmlElement) -> None:
        for xpath in _POST_CLEANUP_XPATHS:
            for element in root.xpath(xpath):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
