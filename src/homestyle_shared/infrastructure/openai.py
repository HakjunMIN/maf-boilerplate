from collections.abc import Awaitable, Callable

from azure.core.credentials import TokenCredential
from azure.identity import get_bearer_token_provider
from openai import AsyncAzureOpenAI

EmbedText = Callable[[str], Awaitable[list[float]]]

_AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIEmbedder:
    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        api_version: str,
        credential: TokenCredential,
    ) -> None:
        token_provider = get_bearer_token_provider(credential, _AZURE_OPENAI_SCOPE)
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
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
        api_version: str,
        credential: TokenCredential,
    ) -> None:
        token_provider = get_bearer_token_provider(credential, _AZURE_OPENAI_SCOPE)
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
        )
        self._deployment = deployment

    async def extract_markdown(self, prompt: str, image_urls: list[str]) -> str:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        *(
                            {"type": "image_url", "image_url": {"url": image_url}}
                            for image_url in image_urls
                        ),
                    ],
                }
            ],
        )
        content = response.choices[0].message.content
        return (content or "").strip()

    async def close(self) -> None:
        await self._client.close()
