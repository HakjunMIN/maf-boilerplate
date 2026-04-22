from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import agent_framework
from azure.identity import DefaultAzureCredential

if not hasattr(agent_framework, "__version__"):
    agent_framework.__version__ = "1.1.0"

from agent_framework._agents import Agent
from agent_framework._clients import SupportsChatGetResponse
from agent_framework._tools import tool

from maf_backend.domain.models import SandboxExecutionResult
from maf_backend.infrastructure.sandbox.runner import DockerSandboxRunner
from maf_backend.settings import Settings


@dataclass(frozen=True)
class AgentExecutionResult:
    summary: str
    generated_code: str
    sandbox_result: SandboxExecutionResult


class AnalysisAgentRunner:
    def __init__(self, settings: Settings, sandbox_runner: DockerSandboxRunner) -> None:
        self._settings = settings
        self._sandbox_runner = sandbox_runner
        self._agent = self._build_agent()

    async def run(self, query: str, input_files: list[str]) -> AgentExecutionResult:
        sandbox_results: list[SandboxExecutionResult] = []
        captured_code: dict[str, str] = {"value": ""}

        @tool
        async def run_code_in_sandbox(code: str) -> dict[str, Any]:
            """Execute Python analysis code inside the isolated Docker sandbox."""
            captured_code["value"] = code
            result = await self._sandbox_runner.run(code, input_files)
            sandbox_results.append(result)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "artifacts": result.artifacts,
            }

        response = await self._agent.run(
            (
                "You are a data analysis agent. Write Python that reads only from mounted files under /inputs, "
                "prints concise findings to stdout, and optionally writes files to /workspace/output. "
                f"User request: {query}. Available input files: {input_files or ['none']}. "
                "Always call run_code_in_sandbox exactly once before giving the final answer."
            ),
            tools=[run_code_in_sandbox],
        )
        if not sandbox_results:
            raise RuntimeError("agent did not invoke the sandbox tool")

        return AgentExecutionResult(
            summary=response.text.strip(),
            generated_code=captured_code["value"],
            sandbox_result=sandbox_results[-1],
        )

    def _build_agent(self) -> Agent[Any]:
        client = self._build_client()
        return Agent[Any](
            name="analysis_agent",
            instructions=(
                "You are a precise data analysis backend agent. "
                "Generate safe Python for structured analysis tasks and rely on the sandbox tool for execution. "
                "Never claim results before tool execution succeeds."
            ),
            client=client,
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
