import hmac
import json
from collections.abc import Mapping

from aiohttp import web

from homestyle_agent.api.http import AuthenticateRequest, InMemorySessionStore, create_app
from homestyle_agent.infrastructure.runtime import AzureRagRuntime
from homestyle_shared.infrastructure.settings import AzureRagSettings, load_environment

_AUTH_TOKEN_ENV = "HOMESTYLE_AGENT_BEARER_TOKEN"
_ENABLE_TRACE_EVALUATION_ENV = "ENABLE_FOUNDRY_TRACE_EVALUATION"
_TRACE_AGENT_ID_ENV = "AZURE_AI_EVALUATION_TRACE_AGENT_ID"


def build_app_from_env(env: Mapping[str, str] | None = None) -> web.Application:
    values = load_environment(env)
    settings = AzureRagSettings.from_env(values)
    token = _read_required_token(values)
    return create_app(
        runtime=AzureRagRuntime(settings, observability_environment=values),
        session_store=InMemorySessionStore(),
        authenticate_request=bearer_token_auth(token),
        enable_trace_evaluation=_is_enabled(values.get(_ENABLE_TRACE_EVALUATION_ENV, "")),
        trace_agent_id=values.get(_TRACE_AGENT_ID_ENV, "homestyle-agent:1").strip()
        or "homestyle-agent:1",
    )


def bearer_token_auth(expected_token: str) -> AuthenticateRequest:
    async def authenticate(request: web.Request) -> None:
        authorization = request.headers.get("Authorization", "")
        expected_header = f"Bearer {expected_token}"
        if not hmac.compare_digest(authorization, expected_header):
            raise _unauthorized_response()

    return authenticate


def main() -> None:
    values = load_environment()
    app = build_app_from_env(values)
    host = values.get("HOST", "127.0.0.1")
    port = int(values.get("PORT", "8080"))
    web.run_app(app, host=host, port=port)


def _read_required_token(env: Mapping[str, str]) -> str:
    token = env.get(_AUTH_TOKEN_ENV, "").strip()
    if not token:
        raise ValueError(f"Missing required API authentication setting: {_AUTH_TOKEN_ENV}")
    return token


def _is_enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _unauthorized_response() -> web.HTTPUnauthorized:
    body = {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "valid bearer token is required.",
    }
    return web.HTTPUnauthorized(
        text=json.dumps(body),
        content_type="application/problem+json",
    )


if __name__ == "__main__":
    main()