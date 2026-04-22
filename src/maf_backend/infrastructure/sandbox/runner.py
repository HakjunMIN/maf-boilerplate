from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from maf_backend.domain.models import SandboxExecutionResult
from maf_backend.settings import Settings


class SandboxError(RuntimeError):
    """Raised when sandbox execution cannot complete."""


class DockerSandboxRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, code: str, input_files: list[str]) -> SandboxExecutionResult:
        if shutil.which("docker") is None:
            raise SandboxError("docker CLI is not installed or not available in PATH")

        resolved_inputs = [self._resolve_input_file(path) for path in input_files]
        container_name = f"maf-analysis-{uuid4().hex}"

        with tempfile.TemporaryDirectory(prefix="maf-analysis-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            script_path = temp_dir / "run.py"
            inputs_dir = temp_dir / "inputs"
            output_dir = temp_dir / "output"
            inputs_dir.mkdir()
            output_dir.mkdir()
            script_path.write_text(code, encoding="utf-8")
            self._stage_inputs(inputs_dir, resolved_inputs)

            command = [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "--network",
                "none",
                "--cpus",
                self._settings.sandbox_cpus,
                "--memory",
                self._settings.sandbox_memory,
                "--pids-limit",
                "128",
                "--user",
                self._settings.sandbox_user,
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "-v",
                f"{temp_dir_name}:/workspace:rw",
                "-v",
                f"{inputs_dir}:/inputs:ro",
            ]

            command.extend(
                [
                    self._settings.sandbox_image,
                    "python",
                    "/workspace/run.py",
                ]
            )

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._settings.sandbox_timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                await self._kill_container(container_name)
                raise SandboxError("sandbox execution timed out") from exc

            decoded_stdout = self._truncate(stdout.decode("utf-8", errors="replace"))
            decoded_stderr = self._truncate(stderr.decode("utf-8", errors="replace"))
            artifacts = sorted(path.name for path in output_dir.iterdir() if path.is_file())
            return SandboxExecutionResult(
                stdout=decoded_stdout,
                stderr=decoded_stderr,
                exit_code=process.returncode or 0,
                artifacts=artifacts,
            )

    async def _kill_container(self, container_name: str) -> None:
        kill_process = await asyncio.create_subprocess_exec(
            "docker",
            "rm",
            "-f",
            container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await kill_process.communicate()

    def _resolve_input_file(self, input_file: str) -> Path:
        candidate = Path(input_file)
        if not candidate.is_absolute():
            candidate = (self._settings.resolved_data_root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        try:
            candidate.relative_to(self._settings.resolved_data_root)
        except ValueError as exc:
            raise SandboxError(f"input file is outside allowed data root: {input_file}") from exc

        if not candidate.exists() or not candidate.is_file():
            raise SandboxError(f"input file not found: {input_file}")

        return candidate

    def _stage_inputs(self, staged_root: Path, resolved_inputs: list[Path]) -> None:
        for input_path in resolved_inputs:
            relative_path = input_path.relative_to(self._settings.resolved_data_root)
            staged_path = staged_root / relative_path
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, staged_path)

    def _truncate(self, value: str) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) <= self._settings.sandbox_output_limit_bytes:
            return value
        truncated = encoded[: self._settings.sandbox_output_limit_bytes].decode("utf-8", errors="ignore")
        return f"{truncated}\n...[truncated]"
