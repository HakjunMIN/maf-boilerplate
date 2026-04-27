from collections.abc import Awaitable, Callable

from azure.core.credentials import TokenCredential
from azure.identity import get_bearer_token_provider
from openai import AsyncAzureOpenAI

EmbedText = Callable[[str], Awaitable[list[float]]]

_AZURE_OPENAI_SCOPE = "https://ai.azure.com/.default"


class AzureOpenAIEmbedder:
    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        credential: TokenCredential,
    ) -> None:
        token_provider = get_bearer_token_provider(credential, _AZURE_OPENAI_SCOPE)
        self._client = AsyncAzureOpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=token_provider,
        )
        self._deployment = deployment

    async def embed_text(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self._deployment,
            input=text,
        )
        return list(response.data[0].embedding)

    async def close(self) -> None:
        await self._client.close()


class AzureOpenAIVisionExtractor:
    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        credential: TokenCredential,
    ) -> None:
        token_provider = get_bearer_token_provider(credential, _AZURE_OPENAI_SCOPE)
        self._client = AsyncAzureOpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=token_provider,
        )
        self._deployment = deployment

    async def extract_markdown(self, prompt: str, image_urls: list[str]) -> str:
        response = await self._client.responses.create(
            model=self._deployment,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        *(
                            {"type": "input_image", "image_url": image_url}
                            for image_url in image_urls
                        ),
                    ],
                }
            ],
        )
        return response.output_text.strip()

    async def close(self) -> None:
        await self._client.close()
