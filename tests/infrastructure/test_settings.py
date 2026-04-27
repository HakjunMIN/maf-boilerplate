import pytest

from homestyle_shared.infrastructure import AzureRagSettings


def test_azure_rag_settings_from_env_loads_required_and_optional_values() -> None:
    settings = AzureRagSettings.from_env(
        {
            "AZURE_OPENAI_ENDPOINT": "https://openai.example",
            "AZURE_OPENAI_API_VERSION": "2025-07-01-preview",
            "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat-deployment",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding-deployment",
            "AZURE_OPENAI_VISION_DEPLOYMENT": "vision-deployment",
            "AZURE_SEARCH_ENDPOINT": "https://search.example",
            "AZURE_SEARCH_INDEX_NAME": "sections",
            "USE_DEVELOPER_CREDENTIALS": "true",
            "MANAGED_IDENTITY_CLIENT_ID": "client-id",
            "SEARCH_TOP": "7",
            "EXTRACTION_VERSION": "v2",
        }
    )

    assert settings == AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2025-07-01-preview",
        azure_openai_chat_deployment="chat-deployment",
        azure_openai_embedding_deployment="embedding-deployment",
        azure_openai_vision_deployment="vision-deployment",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="sections",
        use_developer_credentials=True,
        managed_identity_client_id="client-id",
        search_top=7,
        extraction_version="v2",
    )


def test_azure_rag_settings_from_env_reads_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", " https://openai.example ")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-07-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "chat-deployment")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embedding-deployment")
    monkeypatch.setenv("AZURE_OPENAI_VISION_DEPLOYMENT", "vision-deployment")
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://search.example")
    monkeypatch.setenv("AZURE_SEARCH_INDEX_NAME", "sections")

    settings = AzureRagSettings.from_env()

    assert settings.azure_openai_endpoint == "https://openai.example"
    assert settings.use_developer_credentials is False
    assert settings.managed_identity_client_id is None
    assert settings.search_top == 5
    assert settings.extraction_version == "v1"


@pytest.mark.parametrize(
    ("env", "message"),
    [
        (
            {
                "AZURE_OPENAI_API_VERSION": "2025-07-01-preview",
                "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat",
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding",
                "AZURE_OPENAI_VISION_DEPLOYMENT": "vision",
                "AZURE_SEARCH_ENDPOINT": "https://search.example",
                "AZURE_SEARCH_INDEX_NAME": "sections",
            },
            "AZURE_OPENAI_ENDPOINT",
        ),
        (
            {
                "AZURE_OPENAI_ENDPOINT": "https://openai.example",
                "AZURE_OPENAI_API_VERSION": "2025-07-01-preview",
                "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat",
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding",
                "AZURE_OPENAI_VISION_DEPLOYMENT": "vision",
                "AZURE_SEARCH_ENDPOINT": "https://search.example",
                "AZURE_SEARCH_INDEX_NAME": "sections",
                "USE_DEVELOPER_CREDENTIALS": "sometimes",
            },
            "Invalid boolean for USE_DEVELOPER_CREDENTIALS",
        ),
        (
            {
                "AZURE_OPENAI_ENDPOINT": "https://openai.example",
                "AZURE_OPENAI_API_VERSION": "2025-07-01-preview",
                "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat",
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding",
                "AZURE_OPENAI_VISION_DEPLOYMENT": "vision",
                "AZURE_SEARCH_ENDPOINT": "https://search.example",
                "AZURE_SEARCH_INDEX_NAME": "sections",
                "SEARCH_TOP": "many",
            },
            "Invalid integer for SEARCH_TOP",
        ),
    ],
)
def test_azure_rag_settings_from_env_fails_fast_for_invalid_values(
    env: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        AzureRagSettings.from_env(env)
