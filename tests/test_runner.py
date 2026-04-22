from __future__ import annotations

from types import SimpleNamespace

import pytest

from maf_backend.application.agent import AnalysisAgentRunner
from maf_backend.domain.models import AgentExecutionResult, SandboxExecutionResult
from maf_backend.settings import Settings


class FakeOrchestratorAgent:
    def __init__(self, tool_name: str | None, runner: AnalysisAgentRunner) -> None:
        self._tool_name = tool_name
        self._runner = runner

    async def run(self, prompt: str, tools: list) -> SimpleNamespace:
        if self._tool_name is not None:
            tool_map = {tool.name: tool for tool in tools}
            if self._tool_name == "ask_code_interpreter":
                await tool_map[self._tool_name].invoke(arguments={"task": "count rows"})
            if self._tool_name == "ask_web_researcher":
                await tool_map[self._tool_name].invoke(arguments={"research_query": "latest docs"})
        return SimpleNamespace(text="final summary")


class DummySandboxRunner:
    async def run(self, code: str, input_files: list[str]) -> SandboxExecutionResult:
        return SandboxExecutionResult(stdout="ok", stderr="", exit_code=0, artifacts=[])


@pytest.mark.asyncio
async def test_runner_returns_code_interpreter_result(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = AnalysisAgentRunner(Settings(foundry_local_model="gpt-test"), DummySandboxRunner())

    async def fake_code_run(query: str, input_files: list[str]) -> AgentExecutionResult:
        return AgentExecutionResult(
            summary="code summary",
            generated_code="print('hello')",
            sandbox_result=SandboxExecutionResult(stdout="hello", stderr="", exit_code=0, artifacts=[]),
        )

    monkeypatch.setattr(runner._code_interpreter, "run", fake_code_run)
    runner._agent = FakeOrchestratorAgent("ask_code_interpreter", runner)

    result = await runner.run("analyze file", ["vlm_outputs/sample.csv"])

    assert result.summary == "final summary"
    assert result.generated_code == "print('hello')"
    assert result.sandbox_result is not None
    assert result.sandbox_result.stdout == "hello"


@pytest.mark.asyncio
async def test_runner_returns_web_search_results(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = AnalysisAgentRunner(Settings(foundry_local_model="gpt-test"), DummySandboxRunner())

    async def fake_search_run(query: str):
        from maf_backend.application.agents.web_search import WebSearchResult

        return WebSearchResult(summary="search summary", results=["result one", "result two"])

    monkeypatch.setattr(runner._web_search, "run", fake_search_run)
    runner._agent = FakeOrchestratorAgent("ask_web_researcher", runner)

    result = await runner.run("find docs", [])

    assert result.summary == "final summary"
    assert result.generated_code == ""
    assert result.sandbox_result is None
    assert result.web_search_results == ["result one", "result two"]


@pytest.mark.asyncio
async def test_runner_does_not_require_tool_invocation() -> None:
    runner = AnalysisAgentRunner(Settings(foundry_local_model="gpt-test"), DummySandboxRunner())
    runner._agent = FakeOrchestratorAgent(None, runner)

    result = await runner.run("just answer", [])

    assert result.summary == "final summary"
    assert result.generated_code == ""
    assert result.sandbox_result is None
    assert result.web_search_results == []