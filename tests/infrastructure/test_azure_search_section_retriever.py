import pytest

from homestyle_agent.infrastructure.retrieval import AzureSearchSectionRetriever


@pytest.mark.asyncio
async def test_azure_search_section_retriever_normalizes_section_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_search: dict[str, object] = {}

    class FakeSearchResults:
        def __aiter__(self) -> "FakeSearchResults":
            return self

        async def __anext__(self) -> dict[str, object]:
            if hasattr(self, "_done"):
                raise StopAsyncIteration
            self._done = True
            return {
                "chunk_id": "chunk-1",
                "page_url": "https://homestyle.lge.co.kr/collection/living-room#section-1",
                "locale": "ko",
                "title": "거실 컬렉션",
                "breadcrumb": ["홈", "컬렉션", "거실"],
                "section_heading": "이미지 설명",
                "content": "패브릭 소파 조합입니다.",
                "confidence_score": "0.88",
                "is_image_derived": "true",
                "extraction_version": "v2",
                "reviewer_approved": True,
            }

    class FakeSearchClient:
        def __init__(self, *, endpoint: str, index_name: str, credential: object) -> None:
            self.endpoint = endpoint
            self.index_name = index_name
            self.credential = credential
            self.closed = False

        async def search(self, **kwargs: object) -> FakeSearchResults:
            captured_search.update(kwargs)
            return FakeSearchResults()

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(
        "homestyle_agent.infrastructure.retrieval.SearchClient",
        FakeSearchClient,
    )

    async def embed_query(question: str) -> list[float]:
        assert question == "거실 스타일링을 알려줘"
        return [0.1, 0.2, 0.3]

    retriever = AzureSearchSectionRetriever(
        endpoint="https://search.example",
        index_name="sections",
        credential=object(),
        embed_query=embed_query,
        top=3,
    )

    sections = await retriever.retrieve_sections("거실 스타일링을 알려줘")

    assert captured_search["top"] == 3
    assert captured_search["select"] == [
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
    ]
    assert sections[0].breadcrumb == ("홈", "컬렉션", "거실")
    assert sections[0].section_heading == "이미지 설명"
    assert sections[0].confidence_score == 0.88
    assert sections[0].is_image_derived is True
    assert sections[0].extraction_version == "v2"
    assert sections[0].reviewer_approved is True

    await retriever.close()
