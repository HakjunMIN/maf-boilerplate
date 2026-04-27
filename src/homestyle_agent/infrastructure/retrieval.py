from collections.abc import Awaitable, Callable, Sequence

from azure.core.credentials import TokenCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery

from homestyle_shared.domain.indexing import SectionDocument

EmbedQuery = Callable[[str], Awaitable[list[float]]]


class AzureSearchSectionRetriever:
    def __init__(
        self,
        *,
        endpoint: str,
        index_name: str,
        credential: TokenCredential,
        embed_query: EmbedQuery,
        top: int = 5,
    ) -> None:
        self._client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
        )
        self._embed_query = embed_query
        self._top = top

    async def retrieve_sections(self, question: str) -> list[SectionDocument]:
        question_vector = await self._embed_query(question)
        results = await self._client.search(
            search_text=question,
            vector_queries=[
                VectorizedQuery(
                    vector=question_vector,
                    fields="content_vector",
                    k_nearest_neighbors=self._top,
                )
            ],
            top=self._top,
            select=[
                "chunk_id",
                "page_url",
                "locale",
                "title",
                "breadcrumb",
                "section_heading",
                "content",
                "confidence_score",
                "is_image_derived",
                "extraction_version",
                "reviewer_approved",
            ],
        )

        sections: list[SectionDocument] = []
        async for result in results:
            sections.append(
                SectionDocument(
                    chunk_id=str(result["chunk_id"]),
                    page_url=str(result["page_url"]),
                    locale=str(result["locale"]),
                    title=str(result["title"]),
                    breadcrumb=_normalize_breadcrumb(result.get("breadcrumb")),
                    section_heading=_normalize_text(result.get("section_heading")),
                    content=str(result["content"]),
                    confidence_score=_normalize_float(result.get("confidence_score"), default=1.0),
                    is_image_derived=_normalize_bool(
                        result.get("is_image_derived"),
                        default=False,
                    ),
                    extraction_version=_normalize_text(
                        result.get("extraction_version"),
                        default="v1",
                    ),
                    reviewer_approved=_normalize_bool(
                        result.get("reviewer_approved"),
                        default=False,
                    ),
                )
            )
        return sections

    async def close(self) -> None:
        await self._client.close()


def _normalize_breadcrumb(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value if isinstance(item, str) and item)
    return ()


def _normalize_text(value: object, *, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalize_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _normalize_float(value: object, *, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default
