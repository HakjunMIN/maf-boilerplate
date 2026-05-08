import pytest
from aiohttp.test_utils import TestClient, TestServer

from homestyle_agent.api.server import bearer_token_auth, build_app_from_env
from homestyle_shared.infrastructure import AzureRagSettings


class FakeRuntime:
    async def answer(self, question: str, *, correlation_id: str | None = None) -> str:
        return "authenticated answer"


class FakeConfiguredRuntime:
    def __init__(self, settings: AzureRagSettings) -> None:
        self.settings = settings

    async def answer(self, question: str, *, correlation_id: str | None = None) -> str:
        return f"answer via {self.settings.azure_search_index_name}"


@pytest.mark.asyncio
async def test_bearer_token_auth_rejects_missing_authorization() -> None:
    from homestyle_agent.api import InMemorySessionStore, create_app

    app = create_app(
        runtime=FakeRuntime(),
        session_store=InMemorySessionStore(),
        authenticate_request=bearer_token_auth("expected-token"),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.post("/ask", json={"question": "거실 스타일링"})
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 401
    assert response.content_type == "application/problem+json"
    assert body == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "valid bearer token is required.",
    }


@pytest.mark.asyncio
async def test_bearer_token_auth_allows_matching_authorization() -> None:
    from homestyle_agent.api import InMemorySessionStore, create_app

    app = create_app(
        runtime=FakeRuntime(),
        session_store=InMemorySessionStore(),
        authenticate_request=bearer_token_auth("expected-token"),
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.post(
            "/ask",
            json={"question": "거실 스타일링"},
            headers={"Authorization": "Bearer expected-token"},
        )
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 200
    assert body["answer"] == "authenticated answer"


@pytest.mark.asyncio
async def test_build_app_from_env_loads_root_dotenv_when_running_from_src(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    from pathlib import Path

    project_root = Path(tmp_path)
    source_dir = project_root / "src"
    source_dir.mkdir()
    for name in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_CHAT_DEPLOYMENT",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        "AZURE_OPENAI_VISION_DEPLOYMENT",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_INDEX_NAME",
        "HOMESTYLE_AGENT_BEARER_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    (project_root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (project_root / ".env").write_text(
        "AZURE_OPENAI_ENDPOINT=https://openai.example\n"
        "AZURE_OPENAI_API_VERSION=2025-07-01-preview\n"
        "AZURE_OPENAI_CHAT_DEPLOYMENT=chat-deployment\n"
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding-deployment\n"
        "AZURE_OPENAI_VISION_DEPLOYMENT=vision-deployment\n"
        "AZURE_SEARCH_ENDPOINT=https://search.example\n"
        "AZURE_SEARCH_INDEX_NAME=sections-from-dotenv\n"
        "HOMESTYLE_AGENT_BEARER_TOKEN=expected-token\n"
    )
    monkeypatch.chdir(source_dir)
    monkeypatch.setattr(
        "homestyle_agent.api.server.AzureRagRuntime",
        FakeConfiguredRuntime,
    )

    app = build_app_from_env()
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.post(
            "/ask",
            json={"question": "거실 스타일링"},
            headers={"Authorization": "Bearer expected-token"},
        )
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 200
    assert body["answer"] == "answer via sections-from-dotenv"