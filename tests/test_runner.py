from __future__ import annotations

from pathlib import Path

from maf_backend.infrastructure.sandbox.runner import DockerSandboxRunner
from maf_backend.settings import Settings


def test_stage_inputs_preserves_relative_paths(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    source_file = data_root / "vlm_outputs" / "sample.csv"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("a,b\n1,2\n", encoding="utf-8")

    staged_root = tmp_path / "staged-inputs"
    staged_root.mkdir()

    settings = Settings(API_BEARER_TOKEN="secret", SANDBOX_DATA_ROOT=str(data_root))
    runner = DockerSandboxRunner(settings)

    runner._stage_inputs(staged_root, [source_file])

    staged_file = staged_root / "vlm_outputs" / "sample.csv"
    assert staged_file.exists()
    assert staged_file.read_text(encoding="utf-8") == "a,b\n1,2\n"