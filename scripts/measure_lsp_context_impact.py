import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class CodeUsage:
    path: Path
    line: int
    usage_type: str
    snippet: str


@dataclass(frozen=True)
class FullFileContext:
    files: tuple[Path, ...]
    text: str
    scanned_lines: int
    tokens: int


@dataclass(frozen=True)
class ContextImpact:
    grep_tokens: int
    lsp_tokens: int
    saved_tokens: int
    token_reduction_percent: float
    scanned_lines: int
    focus_lines: int
    focus_multiplier: float
    matched_file_count: int
    usage_count: int


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / 4)


def parse_vscode_lsp_usages(raw_output: str, workspace_root: Path) -> list[CodeUsage]:
    usages: list[CodeUsage] = []
    pattern = re.compile(
        r'<usage type="(?P<usage_type>[^"]+)" uri="(?P<uri>[^"]+)" line="(?P<line>\d+)">\n'
        r'(?P<body>.*?)\n</usage>',
        re.DOTALL,
    )
    for match in pattern.finditer(raw_output):
        uri_path = Path(unquote(urlparse(match.group("uri")).path))
        try:
            path = uri_path.relative_to(workspace_root)
        except ValueError:
            path = uri_path
        snippet = _first_non_empty_line(match.group("body"))
        usages.append(
            CodeUsage(
                path=path,
                line=int(match.group("line")),
                usage_type=match.group("usage_type"),
                snippet=snippet,
            )
        )
    return usages


def collect_literal_file_context(
    workspace_root: Path,
    symbol: str,
    include_patterns: tuple[str, ...] = ("src/**/*.py", "tests/**/*.py", "scripts/**/*.py"),
) -> FullFileContext:
    matched_files: list[Path] = []
    context_parts: list[str] = []
    scanned_lines = 0
    for path in _iter_candidate_files(workspace_root, include_patterns):
        content = path.read_text(encoding="utf-8")
        if symbol not in content:
            continue
        relative_path = path.relative_to(workspace_root)
        matched_files.append(relative_path)
        scanned_lines += len(content.splitlines())
        context_parts.append(f"# {relative_path}\n{content}")
    text = "\n".join(context_parts)
    return FullFileContext(
        files=tuple(matched_files),
        text=text,
        scanned_lines=scanned_lines,
        tokens=estimate_tokens(text),
    )


def build_lsp_usage_context(usages: list[CodeUsage]) -> str:
    lines = [
        f"{usage.path}:{usage.line} [{usage.usage_type}] {usage.snippet}"
        for usage in sorted(usages, key=lambda item: (str(item.path), item.line, item.usage_type))
    ]
    return "\n".join(lines)


def measure_context_impact(
    full_file_context: FullFileContext,
    lsp_usages: list[CodeUsage],
) -> ContextImpact:
    lsp_context = build_lsp_usage_context(lsp_usages)
    lsp_tokens = estimate_tokens(lsp_context)
    saved_tokens = max(full_file_context.tokens - lsp_tokens, 0)
    token_reduction_percent = _percent(saved_tokens, full_file_context.tokens)
    focus_lines = len(lsp_usages)
    focus_multiplier = full_file_context.scanned_lines / focus_lines if focus_lines else 0.0
    return ContextImpact(
        grep_tokens=full_file_context.tokens,
        lsp_tokens=lsp_tokens,
        saved_tokens=saved_tokens,
        token_reduction_percent=round(token_reduction_percent, 1),
        scanned_lines=full_file_context.scanned_lines,
        focus_lines=focus_lines,
        focus_multiplier=round(focus_multiplier, 1),
        matched_file_count=len(full_file_context.files),
        usage_count=len(lsp_usages),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare full-file grep context with VS Code LSP reference context."
    )
    parser.add_argument("symbol", help="Symbol name used for the literal full-file baseline.")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path.cwd(),
        help="Workspace root used to resolve relative paths.",
    )
    parser.add_argument(
        "--lsp-usages-file",
        type=Path,
        required=True,
        help="Text file containing vscode_listCodeUsages output.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Glob to include in the full-file baseline. Can be repeated.",
    )
    args = parser.parse_args()

    include_patterns = tuple(args.include) if args.include else ("src/**/*.py", "tests/**/*.py", "scripts/**/*.py")
    workspace_root = args.workspace_root.resolve()
    full_file_context = collect_literal_file_context(
        workspace_root=workspace_root,
        symbol=args.symbol,
        include_patterns=include_patterns,
    )
    lsp_usages = parse_vscode_lsp_usages(
        args.lsp_usages_file.read_text(encoding="utf-8"),
        workspace_root=workspace_root,
    )
    impact = measure_context_impact(
        full_file_context=full_file_context,
        lsp_usages=lsp_usages,
    )
    print(json.dumps(asdict(impact), ensure_ascii=False, indent=2))


def _iter_candidate_files(workspace_root: Path, include_patterns: tuple[str, ...]) -> list[Path]:
    files: set[Path] = set()
    for pattern in include_patterns:
        files.update(path for path in workspace_root.glob(pattern) if path.is_file())
    return sorted(files)


def _first_non_empty_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _percent(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return part / whole * 100


if __name__ == "__main__":
    main()
