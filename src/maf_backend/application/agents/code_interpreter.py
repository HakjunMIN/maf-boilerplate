from __future__ import annotations

from typing import Any

from agent_framework._agents import Agent
from agent_framework._clients import SupportsChatGetResponse
from agent_framework._tools import tool

from maf_backend.domain.models import AgentExecutionResult, SandboxExecutionResult
from maf_backend.infrastructure.sandbox.runner import DockerSandboxRunner


class CodeInterpreterAgent:
    def __init__(
        self,
        client: SupportsChatGetResponse[Any],
        sandbox_runner: DockerSandboxRunner,
    ) -> None:
        self._client = client
        self._sandbox_runner = sandbox_runner
        self._agent = Agent[Any](
            name="code_interpreter_agent",
            instructions=(
                "You are a code interpreter agent. "
                "Write safe Python for analysis and call run_code_in_sandbox exactly once before responding."
            ),
            client=self._client,
        )

    async def run(self, query: str, input_files: list[str]) -> AgentExecutionResult:
        captured_code: dict[str, str] = {"value": ""}
        sandbox_result: SandboxExecutionResult | None = None

        @tool
        async def run_code_in_sandbox(code: str) -> dict[str, Any]:
            """Execute Python code inside the isolated Docker sandbox."""
            nonlocal sandbox_result
            captured_code["value"] = code
            sandbox_result = await self._sandbox_runner.run(code, input_files)
            return {
                "stdout": sandbox_result.stdout,
                "stderr": sandbox_result.stderr,
                "exit_code": sandbox_result.exit_code,
                "artifacts": list(sandbox_result.artifacts),
            }

        response = await self._agent.run(
            (
                "Use Python when the request requires calculation, structured parsing, or file analysis. "
                f"Request: {query}. Available input files: {input_files or ['none']}."
            ),
            tools=[run_code_in_sandbox],
        )
        if sandbox_result is None:
            raise RuntimeError("code interpreter agent did not invoke the sandbox tool")

        return AgentExecutionResult(
            summary=response.text.strip(),
            generated_code=captured_code["value"],
            sandbox_result=sandbox_result,
        )