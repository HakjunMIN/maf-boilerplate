import pytest

from homestyle_ingestion.infrastructure.indexing import AzureSearchSectionIndexer
from homestyle_shared.domain.indexing import SectionDocument


class FakeSearchResults:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self._results = results
        self._index = 0

    def __aiter__(self) -> "FakeSearchResults":
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, object]:
        if self._index >= len(self._results):
            raise StopAsyncIteration
        result = self._results[self._index]
        self._index += 1
        return result


@pytest.mark.asyncio
async def test_azure_search_section_indexer_uses_section_provenance_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_documents: list[dict[str, object]] = []

    class FakeSearchClient:
        def __init__(self, *, endpoint: str, index_name: str, credential: object) -> None:
            self.endpoint = endpoint
            self.index_name = index_name
            self.credential = credential

        async def merge_or_upload_documents(self, documents: list[dict[str, object]]) -> None:
            captured_documents.extend(documents)

        async def search(self, **_: object) -> FakeSearchResults:
            return FakeSearchResults([])

        async def merge_documents(self, documents: list[dict[str, object]]) -> None:
            return None

        async def delete_documents(self, documents: list[dict[str, object]]) -> None:
            return None

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        "homestyle_ingestion.infrastructure.indexing.SearchClient",
        FakeSearchClient,
    )

    async def embed_content(_: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    indexer = AzureSearchSectionIndexer(
        endpoint="https://search.example",
        index_name="homestyle-sections",
        credential=object(),
        embed_content=embed_content,
        extraction_version="v2",
    )

    await indexer.upsert_sections(
        [
            SectionDocument(
                chunk_id="chunk-1",
                page_url="https://homestyle.lge.co.kr/collection/living-room",
                locale="ko",
                title="거실 컬렉션",
                breadcrumb=("홈", "컬렉션", "거실"),
                section_heading="이미지 설명",
                content="## 이미지 설명\n\n패브릭 소파 조합입니다.",
                confidence_score=0.88,
                is_image_derived=True,
                extraction_version="v2",
                reviewer_approved=True,
            )
        ]
    )

    assert captured_documents
    assert captured_documents[0]["confidence_score"] == 0.88
    assert captured_documents[0]["is_image_derived"] is True
    assert captured_documents[0]["extraction_version"] == "v2"
    assert captured_documents[0]["reviewer_approved"] is True
    assert captured_documents[0]["is_deleted"] is False
    assert captured_documents[0]["deleted_at"] is None


@pytest.mark.asyncio
async def test_azure_search_section_indexer_soft_deletes_existing_page_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_documents: list[dict[str, object]] = []

    class FakeSearchClient:
        def __init__(self, *, endpoint: str, index_name: str, credential: object) -> None:
            self.endpoint = endpoint
            self.index_name = index_name
            self.credential = credential

        async def merge_or_upload_documents(self, documents: list[dict[str, object]]) -> None:
            return None

        async def search(self, **_: object) -> FakeSearchResults:
            return FakeSearchResults([{"chunk_id": "chunk-1"}, {"chunk_id": "chunk-2"}])

        async def merge_documents(self, documents: list[dict[str, object]]) -> None:
            captured_documents.extend(documents)

        async def delete_documents(self, documents: list[dict[str, object]]) -> None:
            return None

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        "homestyle_ingestion.infrastructure.indexing.SearchClient",
        FakeSearchClient,
    )

    async def embed_content(_: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    indexer = AzureSearchSectionIndexer(
        endpoint="https://search.example",
        index_name="homestyle-sections",
        credential=object(),
        embed_content=embed_content,
        extraction_version="v2",
    )

    await indexer.soft_delete_page(
        "https://homestyle.lge.co.kr/collection/living-room",
        "2026-04-28T00:00:00+00:00",
    )

    assert captured_documents == [
        {
            "chunk_id": "chunk-1",
            "is_deleted": True,
            "deleted_at": "2026-04-28T00:00:00+00:00",
        },
        {
            "chunk_id": "chunk-2",
            "is_deleted": True,
            "deleted_at": "2026-04-28T00:00:00+00:00",
        },
    ]


@pytest.mark.asyncio
async def test_azure_search_section_indexer_hard_deletes_existing_page_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_documents: list[dict[str, object]] = []

    class FakeSearchClient:
        def __init__(self, *, endpoint: str, index_name: str, credential: object) -> None:
            self.endpoint = endpoint
            self.index_name = index_name
            self.credential = credential

        async def merge_or_upload_documents(self, documents: list[dict[str, object]]) -> None:
            return None

        async def search(self, **_: object) -> FakeSearchResults:
            return FakeSearchResults([{"chunk_id": "chunk-1"}])

        async def merge_documents(self, documents: list[dict[str, object]]) -> None:
            return None

        async def delete_documents(self, documents: list[dict[str, object]]) -> None:
            captured_documents.extend(documents)

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        "homestyle_ingestion.infrastructure.indexing.SearchClient",
        FakeSearchClient,
    )

    async def embed_content(_: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    indexer = AzureSearchSectionIndexer(
        endpoint="https://search.example",
        index_name="homestyle-sections",
        credential=object(),
        embed_content=embed_content,
        extraction_version="v2",
    )

    await indexer.hard_delete_page("https://homestyle.lge.co.kr/collection/living-room")

    assert captured_documents == [{"chunk_id": "chunk-1"}]
