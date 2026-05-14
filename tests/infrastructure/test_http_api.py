import json
from contextlib import contextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from homestyle_agent.api import InMemorySessionStore, create_app


class FakeRuntime:
    def __init__(self) -> None:
        self.questions: list[str] = []
        self.calls: list[dict[str, str | None]] = []

    async def answer(
        self,
        question: str,
        *,
        correlation_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        self.questions.append(question)
        self.calls.append({"correlation_id": correlation_id, "session_id": session_id})
        return f"answer for {question}"


class FailingRuntime:
    async def answer(
        self,
        question: str,
        *,
        correlation_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        raise RuntimeError("Token tenant does not match resource tenant")


async def allow_request(_: web.Request) -> None:
    return None


@pytest.mark.asyncio
async def test_http_api_answers_and_creates_session() -> None:
    runtime = FakeRuntime()
    app = create_app(
        runtime=runtime,
        session_store=InMemorySessionStore(),
        authenticate_request=allow_request,
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.post("/ask", json={"question": "거실 스타일링을 알려줘"})
        text = await response.text()
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 200
    assert "거실 스타일링을 알려줘" in text
    assert "\\uac70" not in text
    assert body["answer"] == "answer for 거실 스타일링을 알려줘"
    assert isinstance(body["session_id"], str)
    assert body["turn_count"] == 1
    assert runtime.questions == ["거실 스타일링을 알려줘"]
    assert runtime.calls == [
        {"correlation_id": body["session_id"], "session_id": body["session_id"]}
    ]


@pytest.mark.asyncio
async def test_http_api_emits_gen_ai_trace_span_when_enabled(monkeypatch) -> None:
    captured_spans: list[dict[str, object]] = []

    class FakeSpan:
        def __init__(self) -> None:
            self.attributes: dict[str, object] = {}

        def set_attribute(self, key: str, value: object) -> None:
            self.attributes[key] = value

    @contextmanager
    def fake_start_request_span(
        name: str,
        *,
        tracer_name: str,
        attributes: dict[str, object],
    ):
        span = FakeSpan()
        captured_spans.append(
            {
                "name": name,
                "tracer_name": tracer_name,
                "attributes": attributes,
                "span": span,
            }
        )
        yield span

    monkeypatch.setattr("homestyle_agent.api.http.start_request_span", fake_start_request_span)
    runtime = FakeRuntime()
    app = create_app(
        runtime=runtime,
        session_store=InMemorySessionStore(),
        authenticate_request=allow_request,
        enable_trace_evaluation=True,
        trace_agent_id="homestyle-agent:1",
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.post("/ask", json={"question": "거실 스타일링"})
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 200
    assert captured_spans[0]["name"] == "invoke_agent"
    attributes = captured_spans[0]["attributes"]
    assert attributes["gen_ai.operation.name"] == "invoke_agent"
    assert attributes["gen_ai.agent.id"] == "homestyle-agent:1"
    assert attributes["gen_ai.agent.name"] == "homestyle-agent"
    assert attributes["gen_ai.conversation.id"] == body["session_id"]
    assert "거실 스타일링" in str(attributes["gen_ai.input.messages"])
    input_messages = json.loads(str(attributes["gen_ai.input.messages"]))
    assert input_messages[0]["parts"] == [{"type": "text", "content": "거실 스타일링"}]
    span = captured_spans[0]["span"]
    assert "answer for 거실 스타일링" in span.attributes["gen_ai.output.messages"]
    output_messages = json.loads(str(span.attributes["gen_ai.output.messages"]))
    assert output_messages[0]["parts"] == [
        {"type": "text", "content": "answer for 거실 스타일링"}
    ]


@pytest.mark.asyncio
async def test_http_api_preserves_session_turn_count() -> None:
    runtime = FakeRuntime()
    app = create_app(
        runtime=runtime,
        session_store=InMemorySessionStore(),
        authenticate_request=allow_request,
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        first_response = await client.post("/ask", json={"question": "첫 질문"})
        first_body = await first_response.json()
        second_response = await client.post(
            "/ask",
            json={"question": "후속 질문", "session_id": first_body["session_id"]},
        )
        second_body = await second_response.json()
    finally:
        await client.close()

    assert second_response.status == 200
    assert second_body["session_id"] == first_body["session_id"]
    assert second_body["turn_count"] == 2
    assert runtime.questions == ["첫 질문", "후속 질문"]


@pytest.mark.asyncio
async def test_http_api_rejects_invalid_question_without_internal_details() -> None:
    runtime = FakeRuntime()
    app = create_app(
        runtime=runtime,
        session_store=InMemorySessionStore(),
        authenticate_request=allow_request,
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.post("/ask", json={"question": ""})
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 400
    assert response.content_type == "application/problem+json"
    assert body == {
        "type": "about:blank",
        "title": "Invalid request",
        "status": 400,
        "detail": "question must be a non-empty string with at most 500 characters.",
    }
    assert "Traceback" not in str(body)
    assert runtime.questions == []


@pytest.mark.asyncio
async def test_http_api_returns_safe_problem_response_when_runtime_fails() -> None:
    app = create_app(
        runtime=FailingRuntime(),
        session_store=InMemorySessionStore(),
        authenticate_request=allow_request,
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.post("/ask", json={"question": "거실 스타일링"})
        body = await response.json()
    finally:
        await client.close()

    assert response.status == 502
    assert response.content_type == "application/problem+json"
    assert body["type"] == "about:blank"
    assert body["title"] == "Answer generation failed"
    assert body["status"] == 502
    assert body["detail"] == "answer could not be generated from the configured services."
    assert isinstance(body["correlation_id"], str)
    assert "Token tenant" not in str(body)
    assert "Traceback" not in str(body)