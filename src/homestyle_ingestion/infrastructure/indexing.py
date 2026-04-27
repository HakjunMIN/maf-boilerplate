from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime

from azure.core.credentials import TokenCredential
from azure.search.documents.aio import SearchClient

from homestyle_shared.domain.indexing import SectionDocument

EmbedContent = Callable[[str], Awaitable[list[float]]]


class AzureSearchSectionIndexer:
    def __init__(
        self,
        *,
        endpoint: str,
        index_name: str,
        credential: TokenCredential,
        embed_content: EmbedContent,
        extraction_version: str,
    ) -> None:
        self._client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
        )
        self._embed_content = embed_content
        self._extraction_version = extraction_version

    async def upsert_sections(self, sections: Sequence[SectionDocument]) -> None:
        documents = []
        indexed_at = datetime.now(UTC).isoformat()
        for section in sections:
            documents.append(
                {
                    "chunk_id": section.chunk_id,
                    "page_url": section.page_url,
                    "locale": section.locale,
                    "title": section.title,
                    "breadcrumb": list(section.breadcrumb),
                    "section_heading": section.section_heading,
                    "content": section.content,
                    "content_vector": await self._embed_content(section.content),
                    "confidence_score": section.confidence_score,
                    "is_image_derived": section.is_image_derived,
                    "extraction_version": section.extraction_version or self._extraction_version,
                    "reviewer_approved": section.reviewer_approved,
                    "indexed_at": indexed_at,
                }
            )
        if documents:
            await self._client.merge_or_upload_documents(documents)

    async def close(self) -> None:
        await self._client.close()
