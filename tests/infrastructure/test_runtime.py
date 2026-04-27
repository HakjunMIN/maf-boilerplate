import pytest

from homestyle_agent import AzureRagRuntime
from homestyle_shared.domain import SectionDocument
from homestyle_shared.infrastructure import AzureRagSettings


@pytest.mark.asyncio
async def test_azure_rag_runtime_answers_and_closes_via_public_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_events: list[str] = []
    captured_embedder: dict[str, object] = {}
    captured_retriever: dict[str, object] = {}
    captured_generator: dict[str, object] = {}

    class FakeCredential:
        def close(self) -> None:
            close_events.append("credential")

    class FakeEmbedder:
        def __init__(self, *, endpoint: str, deployment: str, credential: object) -> None:
            captured_embedder.update(
                endpoint=endpoint,
                deployment=deployment,
                credential=credential,
            )

        async def embed_text(self, text: str) -> list[float]:
            return [0.1, float(len(text))]

        async def close(self) -> None:
            close_events.append("embedder")

    class FakeRetriever:
        def __init__(
            self,
            *,
            endpoint: str,
            index_name: str,
            credential: object,
            embed_query: object,
            top: int,
        ) -> None:
            captured_retriever.update(
                endpoint=endpoint,
                index_name=index_name,
                credential=credential,
                embed_query=embed_query,
                top=top,
            )

        async def retrieve_sections(self, _: str) -> list[SectionDocument]:
            return [
                SectionDocument(
                    chunk_id="chunk-1",
                    page_url="https://homestyle.lge.co.kr/collection/living-room#section-1",
                    locale="ko",
                    title="거실 컬렉션",
                    breadcrumb=("홈", "컬렉션", "거실"),
                    section_heading="거실 제안",
                    content="패브릭 소파를 중심으로 배치합니다.",
                    confidence_score=0.9,
                    reviewer_approved=True,
                )
            ]

        async def close(self) -> None:
            close_events.append("retriever")

    class FakeGenerator:
        def __init__(
            self,
            *,
            endpoint: str,
            model: str,
            credential: object,
            api_version: str,
        ) -> None:
            captured_generator.update(
                endpoint=endpoint,
                model=model,
                credential=credential,
                api_version=api_version,
            )

        async def generate_grounded_body(
            self,
            question: str,
            sections: list[SectionDocument],
        ) -> str:
            assert question == "거실 스타일링을 알려줘"
            assert len(sections) == 1
            return "패브릭 소파 중심의 거실 구성을 추천합니다."

    monkeypatch.setattr(
        "homestyle_agent.infrastructure.runtime.build_azure_credential",
        lambda **_: FakeCredential(),
    )
    monkeypatch.setattr(
        "homestyle_agent.infrastructure.runtime.AzureOpenAIEmbedder",
        FakeEmbedder,
    )
    monkeypatch.setattr(
        "homestyle_agent.infrastructure.runtime.AzureSearchSectionRetriever",
        FakeRetriever,
    )
    monkeypatch.setattr(
        "homestyle_agent.infrastructure.runtime.MafGroundedBodyGenerator",
        FakeGenerator,
    )

    settings = AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2025-07-01-preview",
        azure_openai_chat_deployment="chat-deployment",
        azure_openai_embedding_deployment="embedding-deployment",
        azure_openai_vision_deployment="vision-deployment",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="sections",
        use_developer_credentials=False,
        managed_identity_client_id=None,
        search_top=4,
        extraction_version="v2",
    )

    runtime = AzureRagRuntime(settings)

    answer = await runtime.answer("거실 스타일링을 알려줘")

    assert answer == (
        "패브릭 소파 중심의 거실 구성을 추천합니다.\n\n"
        "[1] https://homestyle.lge.co.kr/collection/living-room#section-1"
    )
    assert captured_embedder["endpoint"] == "https://openai.example"
    assert captured_embedder["deployment"] == "embedding-deployment"
    assert captured_retriever["endpoint"] == "https://search.example"
    assert captured_retriever["index_name"] == "sections"
    assert captured_retriever["top"] == 4
    assert captured_retriever["embed_query"] == runtime._embedder.embed_text
    assert captured_generator["model"] == "chat-deployment"
    assert captured_generator["api_version"] == "2025-07-01-preview"
    assert captured_embedder["credential"] is captured_retriever["credential"]
    assert captured_retriever["credential"] is captured_generator["credential"]

    await runtime.close()

    assert close_events == ["retriever", "embedder", "credential"]
