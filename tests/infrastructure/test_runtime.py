import pytest

from homestyle_agent.application.grounded_query import GroundedQueryService
from homestyle_agent.application.grounded_query import DECLINE_MESSAGE
from homestyle_agent import AzureRagRuntime
from homestyle_shared.domain import SectionDocument
from homestyle_shared.infrastructure import AzureRagSettings


@pytest.fixture(autouse=True)
def isolate_runtime_observability_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ENABLE_CONSOLE_EXPORTERS",
        "ENABLE_INSTRUMENTATION",
        "ENABLE_SENSITIVE_DATA",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AGENT_FRAMEWORK_OTEL_CONFIGURED",
        False,
    )


@pytest.mark.asyncio
async def test_azure_rag_runtime_answers_and_closes_via_public_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_events: list[str] = []
    captured_embedder: dict[str, object] = {}
    captured_credential: dict[str, object] = {}
    captured_retriever: dict[str, object] = {}
    captured_generator: dict[str, object] = {}

    class FakeCredential:
        def close(self) -> None:
            close_events.append("credential")

    class FakeEmbedder:
        def __init__(
            self,
            *,
            endpoint: str,
            deployment: str,
            api_version: str,
            credential: object,
        ) -> None:
            captured_embedder.update(
                endpoint=endpoint,
                deployment=deployment,
                api_version=api_version,
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
        lambda **kwargs: captured_credential.update(kwargs) or FakeCredential(),
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
        azure_search_admin_key="search-admin-key",
        use_developer_credentials=False,
        azure_tenant_id="tenant-id",
        managed_identity_client_id=None,
        search_top=20,
        extraction_version="v2",
    )

    runtime = AzureRagRuntime(settings)

    answer = await runtime.answer("거실 스타일링을 알려줘")

    assert answer == (
        "패브릭 소파 중심의 거실 구성을 추천합니다.\n\n"
        "[1] 거실 제안 - https://homestyle.lge.co.kr/collection/living-room#section-1"
    )
    assert captured_embedder["endpoint"] == "https://openai.example"
    assert captured_credential == {
        "use_developer_credentials": False,
        "azure_tenant_id": "tenant-id",
        "managed_identity_client_id": None,
    }
    assert captured_embedder["deployment"] == "embedding-deployment"
    assert captured_embedder["api_version"] == "2025-07-01-preview"
    assert captured_retriever["endpoint"] == "https://search.example"
    assert captured_retriever["index_name"] == "sections"
    assert captured_retriever["credential"] is not captured_embedder["credential"]
    assert captured_retriever["credential"].key == "search-admin-key"
    assert captured_retriever["top"] == 5
    assert captured_retriever["embed_query"] == runtime._embedder.embed_text
    assert captured_generator["model"] == "chat-deployment"
    assert captured_generator["api_version"] == "2025-07-01-preview"
    assert captured_embedder["credential"] is captured_generator["credential"]

    await runtime.close()

    assert close_events == ["retriever", "embedder", "credential"]


@pytest.mark.asyncio
async def test_azure_rag_runtime_logs_with_correlation_id(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, object]]] = []

    class FakeLogger:
        def __init__(self, bound_values: dict[str, object] | None = None) -> None:
            self._bound_values = bound_values or {}

        def bind(self, **new_values: object) -> "FakeLogger":
            return FakeLogger({**self._bound_values, **new_values})

        def info(self, event: str, **event_kw: object) -> object:
            events.append((event, {**self._bound_values, **event_kw}))
            return None

    class FakeCredential:
        pass

    class FakeEmbedder:
        def __init__(
            self,
            *,
            endpoint: str,
            deployment: str,
            api_version: str,
            credential: object,
        ) -> None:
            return None

        async def embed_text(self, text: str) -> list[float]:
            return [0.1, float(len(text))]

        async def close(self) -> None:
            return None

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
            return None

        async def retrieve_sections(self, _: str) -> list[SectionDocument]:
            return []

        async def close(self) -> None:
            return None

    class FakeGenerator:
        def __init__(
            self,
            *,
            endpoint: str,
            model: str,
            credential: object,
            api_version: str,
        ) -> None:
            return None

        async def generate_grounded_body(
            self,
            question: str,
            sections: list[SectionDocument],
        ) -> str:
            return ""

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
    )
    runtime = AzureRagRuntime(settings, logger=FakeLogger())

    async def retrieve_sections(_: str) -> list[SectionDocument]:
        return []

    async def generate_grounded_body(_: str, __: list[SectionDocument]) -> str:
        return ""

    runtime.grounded_query_service = GroundedQueryService(
        retrieve_sections=retrieve_sections,
        generate_grounded_body=generate_grounded_body,
    )

    answer = await runtime.answer("거실 스타일링을 알려줘", correlation_id="corr-123")

    assert answer == DECLINE_MESSAGE
    assert events == [
        (
            "grounded_answer_started",
            {"correlation_id": "corr-123", "question_length": len("거실 스타일링을 알려줘")},
        ),
        (
            "grounded_answer_completed",
            {"correlation_id": "corr-123", "answer_length": len(answer), "declined": True},
        ),
    ]


@pytest.mark.asyncio
async def test_azure_rag_runtime_records_span_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    span_calls: list[tuple[str, str, dict[str, object]]] = []
    set_calls: list[tuple[str, object]] = []

    class RecordingSpan:
        def set_attribute(self, key: str, value: object) -> None:
            set_calls.append((key, value))

    @contextmanager
    def fake_start_request_span(name: str, *, tracer_name: str, attributes=None):
        span_calls.append((name, tracer_name, dict(attributes or {})))
        yield RecordingSpan()

    monkeypatch.setattr(
        "homestyle_agent.infrastructure.runtime.start_request_span",
        fake_start_request_span,
    )

    class FakeCredential:
        pass

    class FakeEmbedder:
        def __init__(self, **_: object) -> None:
            return None

        async def embed_text(self, text: str) -> list[float]:
            return [0.0]

        async def close(self) -> None:
            return None

    class FakeRetriever:
        def __init__(self, **_: object) -> None:
            return None

        async def retrieve_sections(self, _: str) -> list[SectionDocument]:
            return []

        async def close(self) -> None:
            return None

    class FakeGenerator:
        def __init__(self, **_: object) -> None:
            return None

        async def generate_grounded_body(
            self,
            question: str,
            sections: list[SectionDocument],
        ) -> str:
            return ""

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
    )
    runtime = AzureRagRuntime(settings)

    answer = await runtime.answer(
        "거실 스타일링을 알려줘",
        correlation_id="corr-xyz",
        session_id="sess-abc",
    )

    assert answer == DECLINE_MESSAGE
    assert span_calls == [
        (
            "homestyle.agent.answer",
            "homestyle_agent.runtime",
            {
                "homestyle.correlation_id": "corr-xyz",
                "homestyle.session_id": "sess-abc",
            },
        )
    ]
    assert ("homestyle.outcome", "declined") in set_calls


def test_azure_rag_runtime_configures_observability_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_configuration: dict[str, object] = {}

    class FakeCredential:
        pass

    class FakeEmbedder:
        def __init__(self, **_: object) -> None:
            return None

        async def embed_text(self, text: str) -> list[float]:
            return [0.1, float(len(text))]

        async def close(self) -> None:
            return None

    class FakeRetriever:
        def __init__(self, **_: object) -> None:
            return None

        async def retrieve_sections(self, _: str) -> list[SectionDocument]:
            return []

        async def close(self) -> None:
            return None

    class FakeGenerator:
        def __init__(self, **_: object) -> None:
            return None

        async def generate_grounded_body(
            self,
            question: str,
            sections: list[SectionDocument],
        ) -> str:
            return ""

    monkeypatch.setattr(
        "homestyle_agent.infrastructure.runtime.configure_process_observability",
        lambda **kwargs: captured_configuration.update(kwargs),
    )
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
        log_level="DEBUG",
        application_insights_connection_string="InstrumentationKey=test",
    )

    AzureRagRuntime(settings)

    assert captured_configuration == {
        "log_level": "DEBUG",
        "application_insights_connection_string": "InstrumentationKey=test",
        "env": None,
    }
