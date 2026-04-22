from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from maf_backend.domain.models import SandboxExecutionResult
from maf_backend.settings import Settings


class DockerSandboxRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._data_root = Path(settings.sandbox_data_root).resolve()

    async def run(self, code: str, input_files: list[str]) -> SandboxExecutionResult:
        workspace = Path(tempfile.mkdtemp(prefix="maf-sandbox-"))
        try:
            inputs_dir = workspace / "inputs"
            output_dir = workspace / "output"
            inputs_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            script_path = workspace / "script.py"
            script_path.write_text(code, encoding="utf-8")

            for relative_path in input_files:
                source = self._resolve_input_path(relative_path)
                target = inputs_dir / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            command = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--cpus",
                self._settings.sandbox_cpus,
                "--memory",
                self._settings.sandbox_memory,
                "--user",
                self._settings.sandbox_user,
                "-v",
                f"{workspace}:/workspace",
                "-v",
                f"{inputs_dir}:/inputs:ro",
                self._settings.sandbox_image,
                "python",
                "/workspace/script.py",
            ]

            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._settings.sandbox_timeout_seconds,
                )
            except TimeoutError:
                process.kill()
                await process.communicate()
                return SandboxExecutionResult(
                    stdout="",
                    stderr="Sandbox execution timed out",
                    exit_code=-1,
                    artifacts=[],
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")[: self._settings.sandbox_output_limit_bytes]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[: self._settings.sandbox_output_limit_bytes]
            artifacts = [
                str(path.relative_to(output_dir))
                for path in sorted(output_dir.rglob("*"))
                if path.is_file()
            ]
            return SandboxExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode or 0,
                artifacts=artifacts,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _resolve_input_path(self, relative_path: str) -> Path:
        candidate = (self._data_root / relative_path).resolve()
        if not str(candidate).startswith(str(self._data_root)):
            raise ValueError(f"Input file escapes data root: {relative_path}")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"Input file not found: {relative_path}")
        return candidate