import pytest

from homestyle_shared.infrastructure.settings import AzureRagSettings, load_environment


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
            "AZURE_SEARCH_ADMIN_KEY": "search-admin-key",
            "USE_DEVELOPER_CREDENTIALS": "true",
            "AZURE_TENANT_ID": "tenant-id",
            "MANAGED_IDENTITY_CLIENT_ID": "client-id",
            "SEARCH_TOP": "7",
            "EXTRACTION_VERSION": "v2",
            "LOG_LEVEL": "DEBUG",
            "APPLICATION_INSIGHTS_CONNECTION_STRING": "InstrumentationKey=test",
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
        azure_search_admin_key="search-admin-key",
        use_developer_credentials=True,
        azure_tenant_id="tenant-id",
        managed_identity_client_id="client-id",
        search_top=7,
        extraction_version="v2",
        log_level="DEBUG",
        application_insights_connection_string="InstrumentationKey=test",
    )


def test_azure_rag_settings_from_env_reads_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("USE_DEVELOPER_CREDENTIALS", raising=False)
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.delenv("MANAGED_IDENTITY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SEARCH_TOP", raising=False)
    monkeypatch.delenv("EXTRACTION_VERSION", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("APPLICATION_INSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", " https://openai.example ")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-07-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "chat-deployment")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embedding-deployment")
    monkeypatch.setenv("AZURE_OPENAI_VISION_DEPLOYMENT", "vision-deployment")
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://search.example")
    monkeypatch.setenv("AZURE_SEARCH_INDEX_NAME", "sections")
    monkeypatch.delenv("AZURE_SEARCH_ADMIN_KEY", raising=False)

    settings = AzureRagSettings.from_env()

    assert settings.azure_openai_endpoint == "https://openai.example"
    assert settings.azure_search_admin_key is None
    assert settings.use_developer_credentials is False
    assert settings.azure_tenant_id is None
    assert settings.managed_identity_client_id is None
    assert settings.search_top == 5
    assert settings.extraction_version == "v1"
    assert settings.log_level == "INFO"
    assert settings.application_insights_connection_string is None


def test_load_environment_reads_root_dotenv_and_prefers_process_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    from pathlib import Path

    project_root = Path(tmp_path)
    source_dir = project_root / "src"
    source_dir.mkdir()
    (project_root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (project_root / ".env").write_text(
        "AZURE_OPENAI_ENDPOINT=https://from-dotenv.example\n"
        "AZURE_SEARCH_INDEX_NAME='sections'\n"
        "USE_DEVELOPER_CREDENTIALS=true\n"
        "# ignored comment\n"
    )
    monkeypatch.chdir(source_dir)

    values = load_environment(
        {
            "AZURE_OPENAI_ENDPOINT": "https://from-process.example",
            "AZURE_OPENAI_API_VERSION": "2025-07-01-preview",
        }
    )

    assert values["AZURE_OPENAI_ENDPOINT"] == "https://from-process.example"
    assert values["AZURE_OPENAI_API_VERSION"] == "2025-07-01-preview"
    assert values["AZURE_SEARCH_INDEX_NAME"] == "sections"
    assert values["USE_DEVELOPER_CREDENTIALS"] == "true"


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
