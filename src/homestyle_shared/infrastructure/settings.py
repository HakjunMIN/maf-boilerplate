from dataclasses import dataclass


@dataclass(frozen=True)
class AzureRagSettings:
    azure_openai_endpoint: str
    azure_openai_api_version: str
    azure_openai_chat_deployment: str
    azure_openai_embedding_deployment: str
    azure_openai_vision_deployment: str
    azure_search_endpoint: str
    azure_search_index_name: str
    use_developer_credentials: bool = False
    managed_identity_client_id: str | None = None
    search_top: int = 5
    extraction_version: str = "v1"
