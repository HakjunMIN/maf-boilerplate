import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Protocol, cast
from uuid import uuid4

from aiohttp import ContentTypeError, web
import structlog

from homestyle_shared.infrastructure.observability import start_request_span

_MAX_QUESTION_LENGTH = 500
_LOGGER = structlog.get_logger("homestyle_agent_http_api")
_TRACE_EVALUATION_SPAN_NAME = "invoke_agent"
_TRACE_EVALUATION_TRACER_NAME = "homestyle_agent.trace_evaluation"
_DEFAULT_TRACE_AGENT_NAME = "homestyle-agent"
_PROBLEM_EXCEPTIONS: dict[int, type[web.HTTPException]] = {
    400: web.HTTPBadRequest,
    502: web.HTTPBadGateway,
}


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class AnswerRuntime(Protocol):
    async def answer(
        self,
        question: str,
        *,
        correlation_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        raise NotImplementedError


AuthenticateRequest = Callable[[web.Request], Awaitable[None]]


@dataclass(frozen=True)
class ConversationTurn:
    question: str
    answer: str


class InMemorySessionStore:
    def __init__(self) -> None:
        self._turns_by_session_id: dict[str, list[ConversationTurn]] = {}

    def ensure_session(self, session_id: str | None) -> str:
        active_session_id = session_id or str(uuid4())
        self._turns_by_session_id.setdefault(active_session_id, [])
        return active_session_id

    def record_turn(self, session_id: str, *, question: str, answer: str) -> int:
        turns = self._turns_by_session_id.setdefault(session_id, [])
        turns.append(ConversationTurn(question=question, answer=answer))
        return len(turns)


_RUNTIME_KEY = web.AppKey("runtime", AnswerRuntime)
_SESSION_STORE_KEY = web.AppKey("session_store", InMemorySessionStore)
_AUTHENTICATE_REQUEST_KEY = web.AppKey("authenticate_request", object)
_ENABLE_TRACE_EVALUATION_KEY = web.AppKey("enable_trace_evaluation", bool)
_TRACE_AGENT_ID_KEY = web.AppKey("trace_agent_id", str)


def create_app(
    *,
    runtime: AnswerRuntime,
    session_store: InMemorySessionStore,
    authenticate_request: AuthenticateRequest,
    enable_trace_evaluation: bool = False,
    trace_agent_id: str = "homestyle-agent:1",
) -> web.Application:
    app = web.Application()
    app[_RUNTIME_KEY] = runtime
    app[_SESSION_STORE_KEY] = session_store
    app[_AUTHENTICATE_REQUEST_KEY] = authenticate_request
    app[_ENABLE_TRACE_EVALUATION_KEY] = enable_trace_evaluation
    app[_TRACE_AGENT_ID_KEY] = trace_agent_id
    app.router.add_post("/ask", _handle_ask)
    app.on_cleanup.append(_close_runtime)
    return app


async def _handle_ask(request: web.Request) -> web.Response:
    authenticate_request = cast(AuthenticateRequest, request.app[_AUTHENTICATE_REQUEST_KEY])
    await authenticate_request(request)

    payload = await _read_json_payload(request)
    question = _read_question(payload)
    requested_session_id = _read_session_id(payload)

    session_store = request.app[_SESSION_STORE_KEY]
    session_id = session_store.ensure_session(requested_session_id)
    runtime = request.app[_RUNTIME_KEY]
    try:
        answer = await _answer_with_optional_trace_evaluation_span(
            runtime=runtime,
            question=question,
            session_id=session_id,
            enable_trace_evaluation=request.app[_ENABLE_TRACE_EVALUATION_KEY],
            trace_agent_id=request.app[_TRACE_AGENT_ID_KEY],
        )
    except Exception as error:
        _LOGGER.warning(
            "answer_generation_failed",
            correlation_id=session_id,
            error_type=type(error).__name__,
        )
        raise _problem_response(
            status=502,
            title="Answer generation failed",
            detail="answer could not be generated from the configured services.",
            correlation_id=session_id,
        ) from error
    turn_count = session_store.record_turn(session_id, question=question, answer=answer)

    return web.json_response(
        {
            "answer": answer,
            "session_id": session_id,
            "turn_count": turn_count,
        },
        dumps=_json_dumps,
    )


async def _answer_with_optional_trace_evaluation_span(
    *,
    runtime: AnswerRuntime,
    question: str,
    session_id: str,
    enable_trace_evaluation: bool,
    trace_agent_id: str,
) -> str:
    if not enable_trace_evaluation:
        return await runtime.answer(
            question,
            correlation_id=session_id,
            session_id=session_id,
        )

    with start_request_span(
        _TRACE_EVALUATION_SPAN_NAME,
        tracer_name=_TRACE_EVALUATION_TRACER_NAME,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.id": trace_agent_id,
            "gen_ai.agent.name": trace_agent_id.split(":", maxsplit=1)[0]
            or _DEFAULT_TRACE_AGENT_NAME,
            "gen_ai.conversation.id": session_id,
            "gen_ai.input.messages": _gen_ai_messages_json("user", question),
        },
    ) as span:
        answer = await runtime.answer(
            question,
            correlation_id=session_id,
            session_id=session_id,
        )
        span.set_attribute("gen_ai.output.messages", _gen_ai_messages_json("assistant", answer))
        return answer


def _gen_ai_messages_json(role: str, text: str) -> str:
    return _json_dumps(
        [
            {
                "role": role,
                "content": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            }
        ]
    )


async def _read_json_payload(request: web.Request) -> dict[str, object]:
    try:
        payload = await request.json()
    except (ContentTypeError, JSONDecodeError):
        raise _problem_response(
            status=400,
            title="Invalid request",
            detail="request body must be valid JSON.",
        )
    if not isinstance(payload, dict):
        raise _problem_response(
            status=400,
            title="Invalid request",
            detail="request body must be a JSON object.",
        )
    return payload


def _read_question(payload: dict[str, object]) -> str:
    value = payload.get("question")
    if not isinstance(value, str):
        raise _invalid_question_response()
    question = value.strip()
    if not question or len(question) > _MAX_QUESTION_LENGTH:
        raise _invalid_question_response()
    return question


def _read_session_id(payload: dict[str, object]) -> str | None:
    value = payload.get("session_id")
    if value is None:
        return None
    if not isinstance(value, str):
        raise _problem_response(
            status=400,
            title="Invalid request",
            detail="session_id must be a string when provided.",
        )
    session_id = value.strip()
    return session_id or None


def _invalid_question_response() -> web.HTTPException:
    return _problem_response(
        status=400,
        title="Invalid request",
        detail="question must be a non-empty string with at most 500 characters.",
    )


def _problem_response(
    *,
    status: int,
    title: str,
    detail: str,
    correlation_id: str | None = None,
) -> web.HTTPException:
    body = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if correlation_id is not None:
        body["correlation_id"] = correlation_id
    exception_type = _PROBLEM_EXCEPTIONS.get(status, web.HTTPInternalServerError)
    return exception_type(
        text=_json_dumps(body),
        content_type="application/problem+json",
    )


async def _close_runtime(app: web.Application) -> None:
    close = getattr(app[_RUNTIME_KEY], "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result