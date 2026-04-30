from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime

from azure.core.credentials_async import AsyncTokenCredential
from azure.search.documents.aio import SearchClient

from homestyle_shared.domain.indexing import SectionDocument

EmbedContent = Callable[[str], Awaitable[list[float]]]


class AzureSearchSectionIndexer:
    def __init__(
        self,
        *,
        endpoint: str,
        index_name: str,
        credential: AsyncTokenCredential,
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
                    "content": section.content,
                    "content_vector": await self._embed_content(section.content),
                    "product_id": section.product_id,
                    "product_name": section.product_name,
                    "confidence_score": section.confidence_score,
                    "is_image_derived": section.is_image_derived,
                    "extraction_version": section.extraction_version or self._extraction_version,
                    "reviewer_approved": section.reviewer_approved,
                    "is_deleted": False,
                    "deleted_at": None,
                    "indexed_at": indexed_at,
                }
            )
        if documents:
            await self._client.merge_or_upload_documents(documents)

    async def soft_delete_page(self, page_url: str, deleted_at: str) -> None:
        documents = [
            {
                "chunk_id": chunk_id,
                "is_deleted": True,
                "deleted_at": deleted_at,
            }
            for chunk_id in await self._list_chunk_ids(page_url)
        ]
        if documents:
            await self._client.merge_documents(documents)

    async def hard_delete_page(self, page_url: str) -> None:
        documents = [{"chunk_id": chunk_id} for chunk_id in await self._list_chunk_ids(page_url)]
        if documents:
            await self._client.delete_documents(documents)

    async def close(self) -> None:
        await self._client.close()

    async def _list_chunk_ids(self, page_url: str) -> list[str]:
        escaped_page_url = page_url.replace("'", "''")
        search_results = await self._client.search(
            search_text="*",
            filter=f"page_url eq '{escaped_page_url}'",
            select=["chunk_id"],
            top=1000,
        )
        chunk_ids: list[str] = []
        async for search_result in search_results:
            chunk_ids.append(str(search_result["chunk_id"]))
        return chunk_ids
