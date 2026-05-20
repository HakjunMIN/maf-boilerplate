import importlib.util
from pathlib import Path
from types import ModuleType


def load_script() -> ModuleType:
    path = Path("scripts/measure_lsp_context_impact.py")
    spec = importlib.util.spec_from_file_location("measure_lsp_context_impact", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_vscode_lsp_usages_reads_reference_locations() -> None:
    script = load_script()
    raw_output = '''50 usages of `DiscoveredUrl`:

<usage type="reference" uri="file:///repo/src/package/module.py" line="8">
    from package.domain import DiscoveredUrl
</usage>
<usage type="definition" uri="file:///repo/src/package/domain.py" line="5">
    class DiscoveredUrl:
</usage>
'''

    usages = script.parse_vscode_lsp_usages(raw_output, workspace_root=Path("/repo"))

    assert usages == [
        script.CodeUsage(
            path=Path("src/package/module.py"),
            line=8,
            usage_type="reference",
            snippet="from package.domain import DiscoveredUrl",
        ),
        script.CodeUsage(
            path=Path("src/package/domain.py"),
            line=5,
            usage_type="definition",
            snippet="class DiscoveredUrl:",
        ),
    ]


def test_measure_context_impact_shows_token_and_focus_gain(tmp_path: Path) -> None:
    script = load_script()
    source_path = tmp_path / "src" / "package" / "service.py"
    test_path = tmp_path / "tests" / "test_service.py"
    source_path.parent.mkdir(parents=True)
    test_path.parent.mkdir(parents=True)
    source_path.write_text(
        "class TargetService:\n"
        + "\n".join(f"    def helper_{index}(self) -> int: return {index}" for index in range(80))
        + "\n",
        encoding="utf-8",
    )
    test_path.write_text(
        "from package.service import TargetService\n\n"
        "def test_target_service() -> None:\n"
        "    assert TargetService().helper_1() == 1\n"
        + "\n".join(f"# padding {index}" for index in range(60))
        + "\n",
        encoding="utf-8",
    )

    full_file_context = script.collect_literal_file_context(
        workspace_root=tmp_path,
        symbol="TargetService",
        include_patterns=("src/**/*.py", "tests/**/*.py"),
    )
    lsp_usages = [
        script.CodeUsage(
            path=Path("src/package/service.py"),
            line=1,
            usage_type="definition",
            snippet="class TargetService:",
        ),
        script.CodeUsage(
            path=Path("tests/test_service.py"),
            line=1,
            usage_type="reference",
            snippet="from package.service import TargetService",
        ),
        script.CodeUsage(
            path=Path("tests/test_service.py"),
            line=4,
            usage_type="reference",
            snippet="assert TargetService().helper_1() == 1",
        ),
    ]

    impact = script.measure_context_impact(
        full_file_context=full_file_context,
        lsp_usages=lsp_usages,
    )

    assert impact.grep_tokens > impact.lsp_tokens
    assert impact.token_reduction_percent >= 90.0
    assert impact.scanned_lines == 145
    assert impact.focus_lines == 3
    assert impact.focus_multiplier >= 40.0
    assert impact.usage_count == 3
