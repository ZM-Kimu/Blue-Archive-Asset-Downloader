from __future__ import annotations

import ast
from pathlib import Path

PYTHON_SOURCE_ROOT = Path("src/ba_downloader")
CSHARP_SOURCE_ROOT = Path("third_party/cn_metadata_exporter")

MAX_PYTHON_LOC = 700
MAX_CSHARP_LOC = 1300
MAX_PYTHON_COMPLEXITY = 150
MAX_CSHARP_DECISIONS = 450

PYTHON_DECISION_NODES = (
    ast.Assert,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.ExceptHandler,
    ast.For,
    ast.If,
    ast.IfExp,
    ast.Match,
    ast.Try,
    ast.While,
    ast.With,
)

PYTHON_LOC_ALLOWLIST: dict[Path, int] = {}
PYTHON_COMPLEXITY_ALLOWLIST: dict[Path, int] = {}
CSHARP_LOC_ALLOWLIST: dict[Path, int] = {}
CSHARP_DECISION_ALLOWLIST: dict[Path, int] = {}

FORBIDDEN_INFRA_EDGES = {
    ("infrastructure.download", "infrastructure.extraction"),
    ("infrastructure.regions", "infrastructure.schema"),
    ("infrastructure.regions", "infrastructure.unity"),
}

INFRA_EDGE_ALLOWLIST: set[tuple[str, str]] = set()


def _meaningful_line_count(path: Path) -> int:
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "//"))
    )


def _module_name(path: Path) -> str:
    relative = path.relative_to("src").with_suffix("").as_posix().replace("/", ".")
    if relative.endswith(".__init__"):
        return relative.removesuffix(".__init__")
    return relative


def _infra_layer(module_name: str) -> str:
    parts = module_name.split(".")
    if len(parts) >= 3 and parts[:2] == ["ba_downloader", "infrastructure"]:
        return ".".join(parts[1:3])
    return ""


def _top_layer(module_name: str) -> str:
    parts = module_name.split(".")
    if len(parts) >= 2 and parts[0] == "ba_downloader":
        return parts[1]
    return ""


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name
                for alias in node.names
                if alias.name.startswith("ba_downloader.")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("ba_downloader.")
        ):
            imports.add(node.module)
    return imports


def _approx_python_complexity(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    complexity = 0
    for node in ast.walk(tree):
        if isinstance(node, PYTHON_DECISION_NODES):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += max(0, len(node.values) - 1)
    return complexity


def _approx_csharp_decisions(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    tokens = (
        " if ",
        " for ",
        " foreach ",
        " while ",
        " case ",
        " catch ",
        " switch ",
        " when ",
        "&&",
        "||",
    )
    return sum(text.count(token) for token in tokens)


def test_python_modules_stay_below_complexity_budget() -> None:
    violations: list[str] = []
    for file_path in PYTHON_SOURCE_ROOT.rglob("*.py"):
        if "__pycache__" in file_path.parts:
            continue
        budget = PYTHON_LOC_ALLOWLIST.get(file_path, MAX_PYTHON_LOC)
        line_count = _meaningful_line_count(file_path)
        if line_count > budget:
            violations.append(f"{file_path}: {line_count} LOC > {budget}")

    assert not violations, "\n".join(violations)


def test_python_modules_stay_below_branching_budget() -> None:
    violations: list[str] = []
    for file_path in PYTHON_SOURCE_ROOT.rglob("*.py"):
        if "__pycache__" in file_path.parts:
            continue
        budget = PYTHON_COMPLEXITY_ALLOWLIST.get(file_path, MAX_PYTHON_COMPLEXITY)
        complexity = _approx_python_complexity(file_path)
        if complexity > budget:
            violations.append(f"{file_path}: complexity {complexity} > {budget}")

    assert not violations, "\n".join(violations)


def test_cn_metadata_exporter_modules_stay_below_complexity_budget() -> None:
    violations: list[str] = []
    for file_path in CSHARP_SOURCE_ROOT.rglob("*.cs"):
        if any(part in {"bin", "obj"} for part in file_path.parts):
            continue
        budget = CSHARP_LOC_ALLOWLIST.get(file_path, MAX_CSHARP_LOC)
        line_count = _meaningful_line_count(file_path)
        if line_count > budget:
            violations.append(f"{file_path}: {line_count} LOC > {budget}")

    assert not violations, "\n".join(violations)


def test_cn_metadata_exporter_modules_stay_below_branching_budget() -> None:
    violations: list[str] = []
    for file_path in CSHARP_SOURCE_ROOT.rglob("*.cs"):
        if any(part in {"bin", "obj"} for part in file_path.parts):
            continue
        budget = CSHARP_DECISION_ALLOWLIST.get(file_path, MAX_CSHARP_DECISIONS)
        decisions = _approx_csharp_decisions(file_path)
        if decisions > budget:
            violations.append(f"{file_path}: decisions {decisions} > {budget}")

    assert not violations, "\n".join(violations)


def test_new_infrastructure_cross_edges_do_not_bypass_boundaries() -> None:
    violations: list[str] = []
    for file_path in PYTHON_SOURCE_ROOT.rglob("*.py"):
        if "__pycache__" in file_path.parts:
            continue
        source_module = _module_name(file_path)
        source_layer = _infra_layer(source_module)
        if not source_layer:
            continue
        for target_module in _internal_imports(file_path):
            target_layer = _infra_layer(target_module)
            edge = (source_layer, target_layer)
            module_edge = (source_module, target_module)
            if (
                edge in FORBIDDEN_INFRA_EDGES
                and module_edge not in INFRA_EDGE_ALLOWLIST
            ):
                violations.append(f"{source_module} -> {target_module}")

    assert not violations, "\n".join(violations)


def test_infrastructure_does_not_depend_on_application_layer() -> None:
    violations: list[str] = []
    for file_path in PYTHON_SOURCE_ROOT.rglob("*.py"):
        if "__pycache__" in file_path.parts:
            continue
        source_module = _module_name(file_path)
        if _top_layer(source_module) != "infrastructure":
            continue
        for target_module in _internal_imports(file_path):
            if _top_layer(target_module) == "application":
                violations.append(f"{source_module} -> {target_module}")

    assert not violations, "\n".join(violations)
