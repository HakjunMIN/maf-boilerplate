import inspect

from homestyle_agent.application.grounded_query import GroundedQueryService
from homestyle_agent.infrastructure.maf import MafGroundedBodyGenerator
from homestyle_agent.infrastructure.retrieval import AzureSearchSectionRetriever
from homestyle_shared.infrastructure.azure_identity import build_azure_credential
from homestyle_shared.infrastructure.observability import (
    StructuredLogger,
    bind_correlation_id,
    build_logger,
    configure_observability,
)
from homestyle_shared.infrastructure.openai import AzureOpenAIEmbedder
from homestyle_shared.infrastructure.settings import AzureRagSettings


class AzureRagRuntime:
    def __init__(
        self,
        settings: AzureRagSettings,
        *,
        logger: StructuredLogger | None = None,
    ) -> None:
        configure_observability(
            log_level=settings.log_level,
            application_insights_connection_string=settings.application_insights_connection_string,
        )
        self._credential = build_azure_credential(
            use_developer_credentials=settings.use_developer_credentials,
            managed_identity_client_id=settings.managed_identity_client_id,
        )
        self._logger = logger or build_logger("azure_rag_runtime")
        self._embedder = AzureOpenAIEmbedder(
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_embedding_deployment,
            api_version=settings.azure_openai_api_version,
            credential=self._credential,
        )
        self.retriever = AzureSearchSectionRetriever(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=self._credential,
            embed_query=self._embedder.embed_text,
            top=settings.search_top,
        )
        self.answer_generator = MafGroundedBodyGenerator(
            endpoint=settings.azure_openai_endpoint,
            model=settings.azure_openai_chat_deployment,
            credential=self._credential,
            api_version=settings.azure_openai_api_version,
        )
        self.grounded_query_service = GroundedQueryService(
            retrieve_sections=self.retriever.retrieve_sections,
            generate_grounded_body=self.answer_generator.generate_grounded_body,
        )

    async def answer(self, question: str, *, correlation_id: str | None = None) -> str:
        logger, _ = bind_correlation_id(self._logger, correlation_id)
        logger.info("grounded_answer_started", question_length=len(question))
        answer = await self.grounded_query_service.answer(question)
        logger.info("grounded_answer_completed", answer_length=len(answer))
        return answer

    async def close(self) -> None:
        await self.retriever.close()
        await self._embedder.close()
        await _close_if_present(self._credential)


async def _close_if_present(resource: object) -> None:
    close = getattr(resource, "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result
