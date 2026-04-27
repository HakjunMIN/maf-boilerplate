import pytest

from homestyle_ingestion.infrastructure.indexing import AzureSearchSectionIndexer
from homestyle_shared.domain.indexing import SectionDocument


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
