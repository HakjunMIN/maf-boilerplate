import inspect

from homestyle_agent.application.grounded_query import GroundedQueryService
from homestyle_agent.infrastructure.maf import MafGroundedBodyGenerator
from homestyle_agent.infrastructure.retrieval import AzureSearchSectionRetriever
from homestyle_shared.infrastructure.azure_identity import build_azure_credential
from homestyle_shared.infrastructure.openai import AzureOpenAIEmbedder
from homestyle_shared.infrastructure.settings import AzureRagSettings


class AzureRagRuntime:
    def __init__(self, settings: AzureRagSettings) -> None:
        self._credential = build_azure_credential(
            use_developer_credentials=settings.use_developer_credentials,
            managed_identity_client_id=settings.managed_identity_client_id,
        )
        self._embedder = AzureOpenAIEmbedder(
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_embedding_deployment,
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

    async def answer(self, question: str) -> str:
        return await self.grounded_query_service.answer(question)

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
