from __future__ import annotations

from typing import Any

import agent_framework
from azure.identity import DefaultAzureCredential

if not hasattr(agent_framework, "__version__"):
    agent_framework.__version__ = "1.1.0"

from agent_framework._agents import Agent
from agent_framework._clients import SupportsChatGetResponse
from agent_framework._tools import tool

from maf_backend.application.agents.code_interpreter import CodeInterpreterAgent
from maf_backend.application.agents.web_search import WebSearchAgent
from maf_backend.domain.models import AgentExecutionResult
from maf_backend.infrastructure.sandbox.runner import DockerSandboxRunner
from maf_backend.settings import Settings


class AnalysisAgentRunner:
    def __init__(self, settings: Settings, sandbox_runner: DockerSandboxRunner) -> None:
        self._settings = settings
        self._sandbox_runner = sandbox_runner
        self._client = self._build_client()
        self._agent = self._build_agent()
        self._code_interpreter = CodeInterpreterAgent(self._client, sandbox_runner)
        self._web_search = WebSearchAgent(self._client, max_results=settings.web_search_max_results)

    async def run(self, query: str, input_files: list[str]) -> AgentExecutionResult:
        code_result: AgentExecutionResult | None = None
        web_search_results: list[str] = []

        @tool
        async def ask_code_interpreter(task: str) -> dict[str, Any]:
            """Delegate computation or file analysis to the code interpreter agent."""
            nonlocal code_result
            code_result = await self._code_interpreter.run(task, input_files)
            sandbox_result = code_result.sandbox_result
            return {
                "summary": code_result.summary,
                "generated_code": code_result.generated_code,
                "stdout": sandbox_result.stdout if sandbox_result is not None else "",
                "stderr": sandbox_result.stderr if sandbox_result is not None else "",
                "exit_code": sandbox_result.exit_code if sandbox_result is not None else None,
                "artifacts": list(sandbox_result.artifacts) if sandbox_result is not None else [],
            }

        @tool
        async def ask_web_researcher(research_query: str) -> dict[str, Any]:
            """Delegate external information gathering to the DuckDuckGo web search agent."""
            result = await self._web_search.run(research_query)
            web_search_results.extend(result.results)
            return {
                "summary": result.summary,
                "results": list(result.results),
            }

        response = await self._agent.run(
            (
                "You are the only user-facing reasoning and planning agent. "
                "You may delegate internally to exactly two subordinate agents: ask_code_interpreter for code execution and file analysis, "
                "and ask_web_researcher for external factual lookup. "
                "Use ask_code_interpreter when provided files or calculation matter. "
                "Use ask_web_researcher only when the answer requires outside information. "
                "Never fabricate tool results and do not call more than three tools total in a request. "
                f"User request: {query}. Available input files: {input_files or ['none']}."
            ),
            tools=[ask_code_interpreter, ask_web_researcher],
        )

        return AgentExecutionResult(
            summary=response.text.strip(),
            generated_code=code_result.generated_code if code_result is not None else "",
            sandbox_result=code_result.sandbox_result if code_result is not None else None,
            web_search_results=web_search_results,
        )

    def _build_agent(self) -> Agent[Any]:
        return Agent[Any](
            name="reasoning_orchestrator_agent",
            instructions=(
                "You are a precise reasoning orchestrator. "
                "Plan before acting, use subordinate agents only when needed, and answer with a direct final response."
            ),
            client=self._client,
        )

    def _build_client(self) -> SupportsChatGetResponse[Any]:
        from agent_framework.openai import OpenAIChatClient

        if self._settings.model_provider == "azure_openai":
            return OpenAIChatClient(
                azure_endpoint=self._require(self._settings.azure_openai_endpoint, "AZURE_OPENAI_ENDPOINT"),
                credential=DefaultAzureCredential(),
                model=self._require(self._settings.azure_openai_model, "AZURE_OPENAI_MODEL"),
            )
        if self._settings.model_provider == "openai":
            return OpenAIChatClient(model=self._require(self._settings.openai_model, "OPENAI_MODEL"))
        from agent_framework.foundry import FoundryLocalClient

        return FoundryLocalClient(model=self._require(self._settings.foundry_local_model, "FOUNDRY_LOCAL_MODEL"))

    @staticmethod
    def _require(value: str | None, variable_name: str) -> str:
        if not value:
            raise RuntimeError(f"Missing required setting: {variable_name}")
        return value
